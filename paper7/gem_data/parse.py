# -*- coding: utf-8 -*-
import asyncio
import json
import os
import time
from pdf2image import convert_from_path
from PIL import Image
import PyPDF2

from vlm_gemini import call_gemini_pdf_api, call_gemini_api

poppler_path = r"C:\Users\86188\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin"
cur_dir = os.path.dirname(os.path.abspath(__file__))

def parse_problem_text(text: str):
    import re
    problems = []
    # Pattern to match a problem block
    pattern = re.compile(
        r'<question>(.*?)</question>.*?<answer>(.*?)</answer>.*?<final_answer>(.*?)</final_answer>.*?<hint>(.*?)</hint>(.*?)(?=(<question>|$))',
        re.DOTALL)
    pos = 0
    while pos < len(text):
        match = pattern.search(text, pos)
        if not match:
            break
        question, answer, final_answer, hint, tail = match.group(1), match.group(2), match.group(3), match.group(4), match.group(5)
        # Try to extract optional <img_ggb>
        img_ggb_match = re.search(r'<img_ggb>(.*?)</img_ggb>', tail, re.DOTALL)
        problem = {
            "question": question.strip(),
            "answer": answer.strip(),
            "final_answer": final_answer.strip(),
            "hint": hint.strip()
        }
        if img_ggb_match:
            problem["img_ggb"] = img_ggb_match.group(1).strip()
        problems.append(problem)
        # Move pos to after this match
        pos = match.end(0)
    return problems

def test_parse_problem_text():
    text = '以下是提取出的题目及解答：\n\n<question>（2023 年全国甲卷（文科））函数 $y=f(x)$ 的图像由 $y=\\cos \\left(2x+\\frac{\\pi}{6}\\right)$ 的图像向左平移 $\\frac{\\pi}{6}$ 个单位长度得到，则 $y=f(x)$ 的图像与直线 $y=\\frac{1}{2} x-\\frac{1}{2}$ 的交点个数为（ ）<br>A、1<br>B、2<br>C、3<br>D、4</question>\n<answer>因为 $y=\\cos \\left(2x+\\frac{\\pi}{6}\\right)$ 向左平移 $\\frac{\\pi}{6}$ 个单位所得函数为 $y=\\cos \\left[2\\left(x+\\frac{\\pi}{6}\\right)+\\frac{\\pi}{6}\\right]=\\cos \\left(2x+\\frac{\\pi}{2}\\right)=-\\sin 2x$，所以 $f(x)=-\\sin 2x$，而 $y=\\frac{1}{2} x-\\frac{1}{2}$ 显然过点 $\\left(0,-\\frac{1}{2}\\right)$ 和点 $(1,0)$。<br>考虑 $2x=-\\frac{3\\pi}{2}$， $2x=\\frac{3\\pi}{2}$， $2x=\\frac{7\\pi}{2}$ 处 $f(x)$ 与 $y=\\frac{1}{2} x-\\frac{1}{2}$ 的大小关系，<br>当 $x=-\\frac{3\\pi}{4}$ 时， $f\\left(-\\frac{3\\pi}{4}\\right)=-\\sin \\left(-\\frac{3\\pi}{2}\\right)=-1$， $y=\\frac{1}{2} \\times\\left(-\\frac{3\\pi}{4}\\right)-\\frac{1}{2}=-\\frac{3\\pi+4}{8}<-1$，<br>当 $x=\\frac{3\\pi}{4}$ 时， $f\\left(\\frac{3\\pi}{4}\\right)=-\\sin \\frac{3\\pi}{2}=1$， $y=\\frac{1}{2} \\times \\frac{3\\pi}{4}-\\frac{1}{2}=\\frac{3\\pi-4}{8}<1$，<br>当 $x=\\frac{7\\pi}{4}$ 时， $f\\left(\\frac{7\\pi}{4}\\right)=-\\sin \\frac{7\\pi}{2}=1$， $y=\\frac{1}{2} \\times \\frac{7\\pi}{4}-\\frac{1}{2}=\\frac{7\\pi-4}{8}>1$，<br>所以由图可知， $y=f(x)$ 与 $y=\\frac{1}{2} x-\\frac{1}{2}$ 的交点个数为 3。</answer>\n<final_answer>C</final_answer>\n<hint>数形结合</hint>\n<img_ggb>\nf(x) = -sin(2x)\ng(x) = 0.5x - 0.5\nPlot(f, -3, 6)\nPlot(g, -3, 6)\n</img_ggb>\n\n<question>（2023 年全国甲卷（文科）） 若 x，y 满足约束条件 $\\begin{cases}3x-2y \\le 3\\\\ -2x+3y \\le 3\\\\ x+y \\ge 1\\end{cases}$，则 $z=3x+2y$ 的最大值为：</question>\n<answer>根据题目的要求绘制出约束条件的可行域，由图可知，当目标函数 $y=-\\frac{3}{2} x+\\frac{z}{2}$ 过点 A 时，Z 有最大值，由 $\\begin{cases}-2x+3y=3\\\\ 3x-2y=3\\end{cases}$ 可得 $\\begin{cases}x=3\\\\ y=3\\end{cases}$，即 A（3,3），<br>所以 $z_{\\max }=3 \\times 3+2 \\times 3=15$。</answer>\n<final_answer>15</final_answer>\n<hint>线性规划</hint>\n<img_ggb>\nl1: 3x - 2y = 3\nl2: -2x + 3y = 3\nl3: x + y = 1\nA = Intersect(l1, l2)\nFillDifference(l1, l2, 0.2)\n</img_ggb>\n\n<question>（2023 年全国甲卷（理科））向量 $|\\vec{a}|=|\\vec{b}|=1$， $|\\vec{c}|=\\sqrt{2}$，且 $\\vec{a}+\\vec{b}+\\vec{c}=\\vec{0}$，则 $\\cos \\langle \\vec{a}-\\vec{c}, \\vec{b}-\\vec{c} \\rangle=$（ ）<br>A、 $-\\frac{1}{5}$<br>B、 $-\\frac{2}{5}$<br>C、 $\\frac{2}{5}$<br>D、 $\\frac{4}{5}$</question>\n<answer>根据题目 $\\vec{a}+\\vec{b}+\\vec{c}=\\vec{0}$ 得 $\\vec{a}+\\vec{b}=-\\vec{c}$，即 $\\vec{a}^{2}+\\vec{b}^{2}+2\\vec{a}\\cdot\\vec{b}=\\vec{c}^{2}$，即 $1+1+2\\vec{a}\\cdot\\vec{b}=2$，所以 $\\vec{a}\\cdot\\vec{b}=0$。<br>如图，设 $\\vec{OA}=\\vec{a}$， $\\vec{OB}=\\vec{b}$， $\\vec{OC}=\\vec{c}$<br>由题得，$OA=OB=1$，$OC=\\sqrt{2}$，$\\Delta OAB$ 是等腰直角三角形，AB 边上的高 $OD=\\frac{\\sqrt{2}}{2}$， $AD=\\frac{\\sqrt{2}}{2}$，所以 $CD=CO+OD=\\sqrt{2}+\\frac{\\sqrt{2}}{2}=\\frac{3\\sqrt{2}}{2}$, $\\tan \\angle ACD=\\frac{AD}{CD}=\\frac{1}{3}$， $\\cos \\angle ACD=\\frac{3}{\\sqrt{10}}$， $\\cos \\langle \\vec{a}-\\vec{c}, \\vec{b}-\\vec{c} \\rangle=\\cos \\angle ACB = \\cos 2\\angle ACD = 2\\cos^2 \\angle ACD - 1 = 2 \\times \\left(\\frac{3}{\\sqrt{10}}\\right)^2 - 1 = \\frac{4}{5}$。</answer>\n<final_answer>D</final_answer>\n<hint>向量几何化</hint>\n<img_ggb>\nO = (0, 0)\nA = (-1, 0)\nB = (1, 0)\nC = (0, sqrt(2))\nVector(O, A)\nVector(O, B)\nVector(O, C)\nPolygon(A, B, C)\n</img_ggb>\n\n<question>（2023 年全国乙卷（文科））正方形 ABCD 的边长是 2，E 是 AB 的中点，则 $\\vec{EC}\\cdot\\vec{ED}=$（ ）<br>A、 $\\sqrt{5}$<br>B、3<br>C、 $2\\sqrt{5}$<br>D、5</question>\n<answer>以 A 为坐标原点建立平面直角坐标系，则 E（1,0），C（2,2），D（0,2），可得 $\\vec{EC}=(1,2)$， $\\vec{ED}=(-1,2)$，所以 $\\vec{EC}\\cdot\\vec{ED}=1\\times(-1)+2\\times 2=3$。</answer>\n<final_answer>B</final_answer>\n<hint>坐标法</hint>\n<img_ggb>\nA = (0, 0)\nB = (2, 0)\nC = (2, 2)\nD = (0, 2)\nE = (1, 0)\nPolygon(A, B, C, D)\nVector(E, C)\nVector(E, D)\n</img_ggb>\n\n<question>（2023 年全国新高考Ⅰ卷）过点（0，-2）与圆 $x^{2}+y^{2}-4x-1=0$ 相切的两条直线的夹角为 $\\alpha$，则 $\\sin \\alpha=$ （）<br>A、1<br>B、 $\\frac{\\sqrt{15}}{4}$<br>C、 $\\frac{\\sqrt{10}}{4}$<br>D、 $\\frac{\\sqrt{6}}{4}$</question>\n<answer>根据题目可以将圆 C 的方程 $x^{2}+y^{2}-4x-1=0$ 化简为 $(x-2)^{2}+y^{2}=5$，则该圆的圆心为（2,0），半径 $r=\\sqrt{5}$，设 $\\angle CPA=\\theta$，则 $\\alpha=2\\theta$，<br>$\\sin \\theta=\\frac{CA}{CP}=\\frac{\\sqrt{5}}{2\\sqrt{2}}$，则 $\\cos \\theta=\\frac{\\sqrt{3}}{2\\sqrt{2}}$，所以 $\\sin \\alpha=\\sin 2\\theta=2 \\cos \\theta \\sin \\theta=\\frac{\\sqrt{15}}{4}$。</answer>\n<final_answer>B</final_answer>\n<hint>圆的切线性质</hint>\n<img_ggb>\nC = (2, 0)\nP = (0, -2)\nCircle(C, sqrt(5))\nTangent(P, c)\n</img_ggb>\n\n<question>（2023 年全国新高考Ⅱ卷）已知椭圆 C： $\\frac{x^{2}}{3}+y^{2}=1$ 的左，右焦点分别为 $F_{1}, F_{2}$，直线 $y=x+m$ 与 C 交于点 A，B 两点， $\\Delta F_{1} AB$ 面积是 $\\Delta F_{2} AB$ 的 2 倍，则 m=（ ）<br>A、 $\\frac{2}{3}$<br>B、 $\\frac{\\sqrt{2}}{2}$<br>C、 $-\\frac{\\sqrt{2}}{3}$<br>D、 $-\\frac{2}{3}$</question>\n<answer>设直线与 X 轴交点为 M，因为 $\\Delta F_{1} AB$ 面积是 $\\Delta F_{2} AB$ 的 2 倍，可得 $F_{1}M=2MF_{2}$，又因为椭圆中 $c^{2}=a^{2}-b^{2}=2$，所以 $F_{1}F_{2}=2\\sqrt{2}$，可得 M 点坐标为 $\\left(\\frac{\\sqrt{2}}{3}, 0\\right)$，代入直线 $y=x+m$ 中可得 $m=-\\frac{\\sqrt{2}}{3}$。</answer>\n<final_answer>C</final_answer>\n<hint>等高模型</hint>\n<img_ggb>\na = sqrt(3)\nb = 1\nc = sqrt(2)\nEllipse((0,0), a, b)\nF1 = (-c, 0)\nF2 = (c, 0)\nm = -sqrt(2)/3\nLine((0, m), (1, 1+m))\n</img_ggb>'
    
    problems = parse_problem_text(text)

    assert len(problems) == 6

async def parse_pdf(pdf_path: str):
    """
    Parse a single PDF to extract math problems using Gemini API.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of extracted problems.
    """
    prompt = f"""\n如果pdf中有例题和解答，请提取出来并按格式返回：
    题目使用<question></question>包裹
    解答使用<answer></answer>包裹
    最终答案用<final_answer></final_answer>包裹
    解法提示用<hint></hint>包裹，注意，解法提示只需要用一个精确的数学术语；
    题干中的图片使用<img_ggb></img_ggb>包裹，内容为用geogebra语言绘制该题目图形的代码，如果题目没有图片，则不需要该标签；
    公式使用LaTeX格式并用$包裹；换行使用<br>；注意要提取所有题目"""

    text = ""
    while True:
        result = await call_gemini_pdf_api(pdf_path=pdf_path, prompt=prompt)
    
        if result:
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        if not text:
            print("call_gemini_pdf_api failed, trying with images")
            try:
                images = convert_from_path(pdf_path, poppler_path=poppler_path)
                # stitch images
                widths, heights = zip(*(i.size for i in images))
                total_height = sum(heights)
                max_width = max(widths)
                new_im = Image.new('RGB', (max_width, total_height))
                y_offset = 0
                for im in images:
                    new_im.paste(im, (0, y_offset))
                    y_offset += im.size[1]
                
                # save stitched image to a temporary file
                temp_image_path = "temp_stitched_image.png"
                new_im.save(temp_image_path)

                # call gemini api with the image
                result = await call_gemini_api(image_path=temp_image_path, prompt=prompt)
                if result:
                    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

                # remove temporary file
                os.remove(temp_image_path)
            except Exception as e:
                print(f"Failed to process with images: {e}")


        if text:
            problems = parse_problem_text(text)
            return problems
    
        time.sleep(1)

async def parse_img(image_path: str):
    """
    Parse a single image to extract math problems using Gemini API.

    Args:
        image_path: Path to the image file.

    Returns:
        List of extracted problems.
    """
    prompt = f"""\n如果图片中有例题和解答，请提取出来并按格式返回：
    题目使用<question></question>包裹
    解答使用<answer></answer>包裹
    最终答案用<final_answer></final_answer>包裹
    解法提示用<hint></hint>包裹，注意，解法提示只需要用一个精确的数学术语；
    题干中的图片使用<img_ggb></img_ggb>包裹，内容为用geogebra语言绘制该题目图形的代码，如果题目没有图片，则不需要该标签；
    公式使用LaTeX格式并用$包裹；换行使用<br>；注意要提取所有题目"""

    text = ""
    result = await call_gemini_api(image_path=image_path, prompt=prompt)
    if result:
        text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    
    if text:
        problems = parse_problem_text(text)
        return problems
    
    return []

def parse_all_files(file_dir="pdf_raw", output_file="problems.json"):
    """
    Parses PDFs to extract math problems and saves to JSON.
    Keys: question, answer, final_answer, sol_hint
    """
    print(f"Parsing files from {file_dir}...")

    parsed_pdfs = set()
    parsed_pdfs_filename = "parsed_pdfs.txt"
    parsed_pdfs_filename = os.path.join(cur_dir, parsed_pdfs_filename)
    if os.path.exists(parsed_pdfs_filename):
        with open(parsed_pdfs_filename, encoding='utf-8') as f:
            parsed_pdfs = set(line.strip() for line in f)

    all_problems = []
    for filename in os.listdir(file_dir):
        file_path = os.path.join(file_dir, filename)
        # 只保留pdf_raw/{file_dir}/及之后的路径
        # file_dir 形如 /abs/path/.../pdf_raw/{subdir}
        # 目标是让save_path为 pdf_raw/{subdir}/filename
        # 先找到file_dir在cur_dir下的相对路径
        rel_dir = os.path.relpath(file_dir, cur_dir)
        save_path = os.path.join(rel_dir, filename)
        if save_path in parsed_pdfs:
            print(f"Skipping already parsed {save_path}")
            continue

        if file_path.endswith(".pdf"):
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    if len(reader.pages) > 50:
                        print(f"Skipping {file_path} because it has more than 50 pages.")
                        continue
            except Exception as e:
                print(f"Failed to read pdf {file_path}: {e}")
                continue

            print(f"Parsing {file_path}...")
            problems = asyncio.run(parse_pdf(file_path))
            if problems:
                all_problems.extend(problems)
                with open(output_file, 'a', encoding='utf-8') as f:
                    for problem in problems:
                        f.write(json.dumps(problem, ensure_ascii=False) + "\n")
                with open(parsed_pdfs_filename, 'a', encoding='utf-8') as f:
                    f.write(save_path + "\n")

        elif file_path.endswith(".png") or file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            print(f"Parsing image {file_path}...")
            problems = asyncio.run(parse_img(file_path))
            if problems:
                all_problems.extend(problems)
                with open(output_file, 'a', encoding='utf-8') as f:
                    for problem in problems:
                        f.write(json.dumps(problem, ensure_ascii=False) + "\n")
                with open(parsed_pdfs_filename, 'a', encoding='utf-8') as f:
                    f.write(save_path + "\n")
    print(f"Parsing completed. {len(all_problems)} problems saved to {output_file}")

if __name__ == "__main__":
    # test_parse_problem_text()
    
    import argparse

    parser = argparse.ArgumentParser(description="Parse PDFs to extract math problems.")
    parser.add_argument("--file_dir", type=str, default="quark", help="Directory containing PDF files to parse.")

    args = parser.parse_args()

    file_dir = f"pdf_raw/{args.file_dir}" # "pdf_raw/amm"
    file_dir = os.path.join(cur_dir, file_dir)

    output_file = f"pdf_parsed/problems_{args.file_dir}.json"
    output_file = os.path.join(cur_dir, output_file)

    parse_all_files(file_dir, output_file)