import json
import os
from llm import Model_API, modelConfig
import asyncio

LLM_MODEL = "doubao1.5"

async def solve_question(question: str, sol_hint: str="") -> str:
    """
    用题干本身去请求大模型进行解题
    Args:
        question: 题干字符串
        sol_hint: 解法提示字符串
    Returns:
        answer: 解答字符串
    """
    global LLM_MODEL

    model = Model_API()

    if len(sol_hint.strip()) > 0:
        prompt = f"""请详细解答以下数学问题，给出完整的解题步骤和最终答案：
题目：{question}
解法提示：{sol_hint}
"""
    else:
        prompt = f"""请详细解答以下数学问题，给出完整的解题步骤和最终答案：
题目：{question}
"""
    
    answer = await model.chat(
        model = modelConfig[LLM_MODEL],
        text = prompt,
        max_token = 10240,
        returnType = "text",
        history = []
    )

    return answer

async def check_answer(problem: dict, llm_answer: str) -> bool:
    """
    检查大模型的解答是否正确
    Args:
        problem: 包含题目和正确答案的字典
        llm_answer: 大模型生成的解答字符串
    Returns:
        is_correct: 布尔值，表示解答是否正确
    """
    global LLM_MODEL

    model = Model_API()

    prompt = f"""请判断以下大模型生成的解答是否正确。题目：{problem['question']}。正确答案：{problem['final_answer']}。大模型解答：{llm_answer}。请仅回答“true”或“false”，表示解答是否正确。"""

    response = await model.chat(
        model = modelConfig[LLM_MODEL],
        text = prompt,
        max_token = 200,
        returnType = "text",
        history = []
    )

    return response.strip().lower() == 'true'

async def check_answer_same(problem: dict, llm_answer: str) -> bool:
    """
    检查大模型的解答是否和给出的解答过程采取相同的思路
    Args:
        problem: 包含题目和正确答案的字典
        llm_answer: 大模型生成的解答字符串
    Returns:
        is_same: 布尔值，表示解答是否和给出的解答过程采取相同的思路
    """
    global LLM_MODEL

    model = Model_API()

    prompt = f"""请判断以下大模型生成的解答是否和给出的解答过程采取相同的思路。题目：{problem['question']}。给出的解答过程：{problem['answer']}。大模型解答：{llm_answer}。请仅回答“true”或“false”，表示解答是否和给出的解答过程采取相同的思路。"""

    response = await model.chat(
        model = modelConfig[LLM_MODEL],
        text = prompt,
        max_token = 200,
        returnType = "text",
        history = []
    )

    return response.strip().lower() == 'true'

def solve_questions(
        input_file: str="problems_amm.json", 
        output_file: str="problems_amm_llm.json"
    ):
    """
    读取题目文件，使用大模型进行解题，并将结果保存到输出文件中
    Args:
        input_file: 输入题目文件路径
        {"question": "XXX", "answer": "XXX", "final_answer": "XXX", "hint": "XXX", "img_ggb": "XXX"}
        output_file: 输出解答文件路径
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        problems = []
        for line in f:
            problems.append(json.loads(line.strip()))

    solved_problems = []
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                p = json.loads(line.strip())
                solved_problems[p["question"]] = 1

    for problem in problems:
        question = problem["question"]
        if question in solved_problems:
            print(f"Skipping already solved question: {question}")
            continue

        answer = asyncio.run(solve_question(question))
        answer_is_true = asyncio.run(check_answer(problem, answer))
        answer_is_same = asyncio.run(check_answer_same(problem, answer))
        
        if answer_is_true and answer_is_same:
            problem["llm_answer"] = answer
            problem["llm_answer_is_true"] = answer_is_true
            problem["llm_answer_is_elegant"] = answer_is_same
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(problem, ensure_ascii=False) + '\n')
        else:
            print(f"Failed to get answer for question: {question}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Solve math problems using LLM.")
    parser.add_argument("--model", type=str, default="doubao1.5", help="Model name to use.")
    parser.add_argument("--input_file", type=str, default="pdf_parsed/problems_amm.json", help="Input file with problems.")
    
    args = parser.parse_args()

    LLM_MODEL = args.model

    output_file = args.input_file.replace(".json", f"_{args.model}.json")

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(cur_dir, args.input_file)
    output_file = os.path.join(cur_dir, output_file)

    solve_questions(input_file, output_file)
