import os
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin

BASE_URL = "https://aam.oajrc.org"
START_URL = "https://aam.oajrc.org/Periodical_qkcm.aspx"
OUTPUT_DIR = "amm"
METADATA_FILE = "amm/papers_metadata.json"

def is_relevant(title, abstract):
    """
    Check if the paper is related to middle school math problem solving techniques.
    """
    text = (title + " " + abstract).lower()
    
    # Keywords for education level
    level_keywords = ["中学", "高中", "初中", "高考", "中考", "高一", "高二", "高三", "初一", "初二", "初三",
                      "middle school", "high school", "secondary school", "junior high", "senior high"]
    # Keywords for math (it is a math journal, but good to check)
    math_keywords = ["数学", "函数", "几何", "代数", "数列", "方程", "不等式", "导数", "向量",
                     "math", "mathematics", "algebra", "geometry", "calculus", "function"]
    # Keywords for problem solving/techniques
    technique_keywords = ["解题", "技巧", "方法", "策略", "思路", "应用", "探究", "分析", "研究",
                          "problem solving", "technique", "method", "strategy", "approach", "analysis"]

    has_level = any(k in text for k in level_keywords)
    has_math = any(k in text for k in math_keywords)
    has_technique = any(k in text for k in technique_keywords)

    # Relaxed condition: If it mentions middle school/high school and math, it's likely relevant given the user's request context.
    # Or if it mentions specific math topics often taught in high school + problem solving.
    
    if has_level and has_math:
        return True
    
    return False

import urllib3
import re
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def sanitize_filename(name):
    # Remove invalid characters for Windows filenames: < > : " / \ | ? *
    return re.sub(r'[<>:"/\\|?*]', '', name)

def download_pdf(url, save_path):
    try:
        response = requests.get(url, stream=True, timeout=60, verify=False)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            print(f"Failed to download PDF: {url} (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"Error downloading PDF {url}: {e}")
        return False

def scrape():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    session.headers.update(headers)
    session.verify = False

    print(f"Fetching issue list from {START_URL}...")
    try:
        response = session.get(START_URL, verify=False)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch start page: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all issues
    issue_links = []
    ul_lmlb = soup.find('ul', class_='lmlb')
    if ul_lmlb:
        for li in ul_lmlb.find_all('li'):
            a = li.find('a')
            if a and 'href' in a.attrs:
                link = urljoin(BASE_URL, a['href'])
                name = a.get_text(strip=True)
                issue_links.append((name, link))
    
    print(f"Found {len(issue_links)} issues.")

    all_papers = []

    for issue_name, issue_url in issue_links:
        # Limit for testing if needed, but let's just print more info
        print(f"Processing issue: {issue_name} ({issue_url})")
        try:
            r = session.get(issue_url, timeout=30, verify=False)
            if r.status_code != 200:
                print(f"Failed to fetch issue page: {issue_url}")
                continue
            
            issue_soup = BeautifulSoup(r.text, 'html.parser')
            article_list = issue_soup.find('div', class_='qkwz')
            
            if not article_list:
                print("No article list found.")
                continue

            articles = article_list.find_all('div', class_='zxart')
            print(f"  Found {len(articles)} articles.")
            for art in articles:
                # Extract Title
                h2 = art.find('h2')
                title = h2.get_text(strip=True) if h2 else "No Title"
                
                # Extract Abstract
                p_abstr = art.find('p', class_='abstr')
                abstract = p_abstr.get_text(strip=True) if p_abstr else ""
                
                # Extract PDF Link
                pdf_link = None
                # Look for the link that contains PDF text or is in the specific span
                # Based on user snippet: <span>全文下载：<a href="...">【PDF】</a> </span>
                for a_tag in art.find_all('a'):
                    if 'pdf' in a_tag.get('href', '').lower() or 'PDF' in a_tag.get_text():
                        pdf_link = urljoin(BASE_URL, a_tag['href'])
                        break
                
                is_target = is_relevant(title, abstract)
                # print(f"  Checking: {title[:30]}... Target: {is_target}")
                
                paper_info = {
                    "issue": issue_name,
                    "title": title,
                    "abstract": abstract,
                    "pdf_url": pdf_link,
                    "is_target": is_target,
                    "local_path": None
                }

                if is_target and pdf_link:
                    print(f"  [MATCH] Found relevant paper: {title}")
                    safe_title = sanitize_filename(title[:50])
                    filename = f"{safe_title}.pdf"
                    save_path = os.path.join(OUTPUT_DIR, filename)
                    
                    if not os.path.exists(save_path):
                        print(f"  Downloading to {save_path}...")
                        if download_pdf(pdf_link, save_path):
                            paper_info["local_path"] = save_path
                            time.sleep(1) # Be polite
                    else:
                        print(f"  File already exists: {save_path}")
                        paper_info["local_path"] = save_path
                else:
                    # print(f"  [SKIP] {title}")
                    pass

                all_papers.append(paper_info)
            
            # Sleep between issues
            time.sleep(1)

        except Exception as e:
            print(f"Error processing issue {issue_name}: {e}")
            import traceback
            traceback.print_exc()

    # Save metadata
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)
    
    print(f"Done. Metadata saved to {METADATA_FILE}")

import argparse

def check_downloads():
    """
    Checks existing metadata and ensures all target PDFs are downloaded.
    Useful for fixing failed downloads without re-scraping.
    """
    if not os.path.exists(METADATA_FILE):
        print(f"Metadata file {METADATA_FILE} not found. Please run scrape first.")
        return

    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        papers = json.load(f)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    updated = False
    missing_count = 0
    
    print(f"Checking {len(papers)} papers from metadata...")

    for paper in papers:
        # Check both keys for compatibility
        is_target = paper.get("is_target") or paper.get("tag")
        
        if is_target:
            title = paper.get("title", "No Title")
            pdf_url = paper.get("pdf_url")
            local_path = paper.get("local_path")

            # Reconstruct expected filename to check existence even if local_path is set
            safe_title = sanitize_filename(title[:50])
            expected_filename = f"{safe_title}.pdf"
            expected_path = os.path.join(OUTPUT_DIR, expected_filename)

            needs_download = False
            
            # Case 1: Metadata says we have it, but file is missing
            if local_path and not os.path.exists(local_path):
                print(f"[MISSING FILE] {title}")
                print(f"  Path in metadata: {local_path}")
                needs_download = True
            
            # Case 2: Metadata says we don't have it (local_path is null)
            elif not local_path:
                print(f"[NOT DOWNLOADED] {title}")
                needs_download = True
            
            # Case 3: Check if the expected path exists even if metadata is null (recovery)
            if not local_path and os.path.exists(expected_path):
                print(f"  Found file at expected path, updating metadata.")
                paper["local_path"] = expected_path
                updated = True
                needs_download = False

            if needs_download and pdf_url:
                print(f"  Downloading from {pdf_url}...")
                if download_pdf(pdf_url, expected_path):
                    print(f"  Success.")
                    paper["local_path"] = expected_path
                    updated = True
                    time.sleep(1) # Be polite
                else:
                    print(f"  Failed to download.")
                    missing_count += 1
            elif needs_download and not pdf_url:
                print(f"  No PDF URL available.")
                missing_count += 1

    if updated:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        print(f"Updated metadata saved to {METADATA_FILE}")
    else:
        print("No changes made to metadata.")

    if missing_count > 0:
        print(f"There are still {missing_count} missing PDFs.")
    else:
        print("All target PDFs are downloaded.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape papers or check downloads.")
    parser.add_argument("--check", action="store_true", help="Check and fix missing downloads based on existing metadata")
    args = parser.parse_args()

    if args.check:
        check_downloads()
    else:
        scrape()
