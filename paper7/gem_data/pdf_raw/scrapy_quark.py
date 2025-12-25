import os
import glob
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import re
import time
import requests
from PIL import Image
from io import BytesIO

def parse_htmls():
    """Main function to parse HTML, to get links."""    
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(cur_dir)
    
    html_files = glob.glob('quark*.html')
    if not html_files:
        print("No 'quark*.html' files found.")
        return

    for html_file in html_files:
        print(f"Parsing {html_file}...")
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # This selector might need to be adjusted based on the actual HTML structure.
        # This example assumes links are in <a> tags and titles are their text.
        all_links = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href not in all_links:
                all_links.append(href)
        all_titles = [x.get_text(strip=True) for x in soup.select('div.qk-title-text.qk-font-normal')]

        for link, title in zip(all_links, all_titles):
            print(link)

def scrape_and_stitch_document(driver, url: str, output_image: str):
    """
    Scrapes a document from a given URL, clicks through "continue reading",
    downloads all page images, and stitches them into a single vertical image.
    Uses an existing webdriver instance.
    """
    IMAGE_SELECTOR = "img._curr-img_1arrx_9, img.ant-image-img, img.img-div-content, img.css-198drv2"
    try:
        print(f"Opening URL: {url}")
        driver.get(url)

        # 1. Get total number of pages
        try:
            page_info_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "._V617Rc4Veh1fTxTzgg2"))
            )
            spans = page_info_element.find_elements(By.TAG_NAME, "span")
            page_text = spans[2].text  # "11页"
            total_pages = int(re.search(r'\d+', page_text).group())
            print(f"Document has {total_pages} pages.")
        except Exception as e:
            print(f"Could not determine total pages: {e}")
            total_pages = 0 # Fallback

        # 2. Scroll and click "Continue Reading"
        print("Scrolling to load all pages...")
        last_image_count = 0
        no_change_count = 0
        while True:
            # 1. Targeted Scrolling: Scroll the actual document container
            driver.execute_script("""
                var container = document.getElementById('scroll-container');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
                // Also try to scroll any other potential containers
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {
                    var style = window.getComputedStyle(elements[i]);
                    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && 
                        elements[i].scrollHeight > elements[i].clientHeight) {
                        elements[i].scrollTop = elements[i].scrollHeight;
                    }
                }
            """)
            time.sleep(2) # Wait for content to load

            # 2. Try to find and click the "continue reading" button via JS (more reliable)
            try:
                clicked = driver.execute_script("""
                    // Hide potential blocking selection layers
                    var blockers = document.querySelectorAll('[class*="_pc-selection_"], [class*="selection-layer"]');
                    blockers.forEach(el => el.style.pointerEvents = 'none');

                    var btn = document.querySelector('._continue-read_1tndn_1') || 
                              document.querySelector('._continue-read-mask_1tndn_1') ||
                              document.querySelector('[class*="continue-read"]') ||
                              Array.from(document.querySelectorAll('div, button, span')).find(el => 
                                  (el.textContent.includes('继续浏览') || el.textContent.includes('继续阅读')) && 
                                  el.offsetWidth > 0 && el.offsetHeight > 0
                              );
                    if (btn) {
                        btn.scrollIntoView({block: 'center'});
                        // Force it to be clickable
                        btn.style.pointerEvents = 'auto';
                        btn.style.visibility = 'visible';
                        btn.style.opacity = '1';
                        
                        btn.click();
                        // Try dispatching a real click event as well
                        var ev = new MouseEvent('click', {
                            'view': window,
                            'bubbles': true,
                            'cancelable': true
                        });
                        btn.dispatchEvent(ev);
                        return true;
                    }
                    return false;
                """)
                
                if clicked:
                    print("Found and clicked 'Continue Reading' button via JS.")
                    time.sleep(3)
                    no_change_count = 0
                    # Force remove height restrictions just in case
                    driver.execute_script("""
                        var list = document.querySelector('._preview-list_1oziv_1');
                        if (list) {
                            list.style.maxHeight = 'none';
                            list.style.overflow = 'visible';
                        }
                    """)
                    return
                    # continue
            except Exception as e:
                print(f"Note: Error during JS click: {e}")

            # Check if we are still loading new images
            current_image_count = len(driver.find_elements(By.CSS_SELECTOR, IMAGE_SELECTOR))
            print(f"Images loaded: {current_image_count}")
            
            if current_image_count > last_image_count:
                last_image_count = current_image_count
                no_change_count = 0
            else:
                no_change_count += 1
            
            # If total_pages is known, we can use it as a stop condition
            if total_pages > 0 and current_image_count >= total_pages:
                print(f"Reached total pages ({total_pages}).")
                break
                
            if no_change_count >= 2:
                print("No more images loading after multiple attempts. Assuming end of document.")
                break
        
        # 3. Find all page images
        print("Finding all page images...")
        # Wait until at least one image is loaded
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, IMAGE_SELECTOR))
        )
        image_elements = driver.find_elements(By.CSS_SELECTOR, IMAGE_SELECTOR)
        image_urls = [el.get_attribute('src') for el in image_elements if el.get_attribute('src')]
        print(f"Found {len(image_urls)} page images.")

        if not image_urls:
            print("No images found to download.")
            return

        # 4. Download and stitch images
        print("Downloading and stitching images...")
        
        # Prepare session with cookies and headers from Selenium
        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])
        
        user_agent = driver.execute_script("return navigator.userAgent;")
        headers = {
            'User-Agent': user_agent,
            'Referer': url,
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        images = []
        for i, img_url in enumerate(image_urls):
            try:
                print(f"Downloading image {i+1}/{len(image_urls)}...")
                # Use the session with headers to avoid 403 Forbidden
                response = session.get(img_url, headers=headers, timeout=15)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                images.append(img)
            except Exception as e:
                print(f"Failed to download or process image {img_url}: {e}")
                continue
        
        if not images:
            print("Image download failed for all URLs.")
            return

        # Stitching logic
        total_width = max(img.width for img in images)
        total_height = sum(img.height for img in images)
        
        stitched_image = Image.new('RGB', (total_width, total_height))
        
        current_height = 0
        for img in images:
            stitched_image.paste(img, (0, current_height))
            current_height += img.height
            
        stitched_image.save(output_image)
        print(f"Successfully stitched and saved image to {output_image}")

    except Exception as e:
        print(f"An error occurred while processing {url}: {e}")
    # The finally block with driver.quit() is removed from here.

if __name__ == '__main__':
    # parse_htmls()

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    output_image_dir = os.path.join(cur_dir, 'screenshots')
    urls_file = os.path.join(cur_dir, 'quark_urls.txt')
    if not os.path.exists(urls_file):
        print(f"Error: '{urls_file}' not found.")
        exit()
    
    os.makedirs(output_image_dir, exist_ok=True)
    existing_images = glob.glob(os.path.join(output_image_dir, '*.png'))
    print(f"Found {len(existing_images)} existing stitched images in '{output_image_dir}'.")

    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line for line in f.readlines() if line.strip()]

    if not urls:
        print("No valid URLs found in quark_urls.txt.")
        exit()

    # --- Initialize WebDriver once, before the loop ---
    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1200,900')
    driver = webdriver.Chrome(service=Service('D:\\chromedriver-win64\\chromedriver.exe'), options=chrome_options)

    try:
        # --- Load first page and wait for user to log in ---
        first_url = urls[0].strip()
        print(f"Opening the first URL for you to log in: {first_url}")
        driver.get(first_url)
        input(">>> Please log in to the website in the browser window. Once you are logged in, press Enter in this terminal to continue...")
        print("\nLogin detected, starting the scraping process...")

        # --- Process all URLs ---
        for i, url in enumerate(urls):
            url = url.strip()
            
            # The first URL is already open, but we re-process it in a logged-in state.
            # For subsequent URLs, the driver will navigate to them.
            print("-" * 50)
            print(f"Processing URL {i+1}/{len(urls)}: {url}")

            # Sanitize the URL to create a valid filename
            sanitized_name = re.sub(r'[\\/*?:"<>|]', "", url.split('/')[-1])
            if not sanitized_name:
                sanitized_name = f"file_{hash(url)}"

            output_image = os.path.join(output_image_dir, f"{sanitized_name}.png")
            if os.path.exists(output_image):
                print(f"Output image '{output_image}' already exists. Skipping...")
                continue

            # Pass the driver instance to the function
            scrape_and_stitch_document(driver, url, output_image)

    finally:
        # --- Quit WebDriver once, after the loop ---
        print("-" * 50)
        print("All URLs processed. Closing browser.")
        driver.quit()