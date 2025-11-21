#!/usr/bin/env python3
"""
ERMR Benchmark Evaluation Script
用于评估大模型在Elegance-Required Mathematical Reasoning任务上的表现
"""

import json
import os
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
import numpy as np
from tqdm import tqdm

# TODO: 根据实际使用的API调整导入
# from openai import OpenAI
# from anthropic import Anthropic
# import google.generativeai as genai


@dataclass
class Problem:
    """数学问题数据结构"""
    id: str
    category: str  # "variable_substitution", "geometric", etc.
    problem_text: str
    answer: str
    elegant_steps: int
    bruteforce_steps: int
    hint: str  # 用于strategy hint prompting


@dataclass
class Solution:
    """模型生成的解答"""
    problem_id: str
    model_name: str
    prompt_strategy: str
    raw_output: str
    extracted_answer: str
    is_correct: bool
    solution_type: str  # "elegant", "brute-force", "hybrid", "invalid"
    step_count: int
    elegance_score: float


class ERMRBenchmark:
    """ERMR Benchmark评估器"""
    
    def __init__(self, data_dir: str = "./ermr_data"):
        self.data_dir = data_dir
        self.problems = self.load_problems()
        self.results = []
        
    def load_problems(self) -> List[Problem]:
        """加载问题集"""
        # TODO: 实现从JSON文件加载
        problems = []
        problem_file = os.path.join(self.data_dir, "problems.json")
        
        if os.path.exists(problem_file):
            with open(problem_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    problems.append(Problem(**item))
        else:
            print(f"Warning: {problem_file} not found. Using empty problem set.")
            
        return problems
    
    def get_prompt(self, problem: Problem, strategy: str = "zero_shot") -> str:
        """
        根据策略生成prompt
        
        Args:
            problem: 问题对象
            strategy: "zero_shot", "strategy_hint", "one_shot_elegant", "cot"
        """
        base_prompt = f"Solve the following mathematical problem:\n\n{problem.problem_text}"
        
        if strategy == "zero_shot":
            return base_prompt
        
        elif strategy == "strategy_hint":
            return f"{base_prompt}\n\nHint: {problem.hint}"
        
        elif strategy == "one_shot_elegant":
            # TODO: 添加相似问题的优雅解法示例
            example = self._get_similar_example(problem)
            return f"Here's an example of elegant problem-solving:\n\n{example}\n\n{base_prompt}"
        
        elif strategy == "cot":
            return f"{base_prompt}\n\nLet's solve this step by step."
        
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _get_similar_example(self, problem: Problem) -> str:
        """获取相似问题的示例（用于one-shot）"""
        # TODO: 实现基于category的示例选择
        return "Example problem and elegant solution..."
    
    def query_model(self, model_name: str, prompt: str, 
                   temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        查询模型API
        
        Args:
            model_name: 模型名称 (e.g., "gpt-4", "llama-2-7b")
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大生成长度
        """
        # TODO: 根据model_name选择对应的API
        
        if model_name.startswith("gpt"):
            # OpenAI API
            # client = OpenAI()
            # response = client.chat.completions.create(...)
            pass
        
        elif model_name.startswith("claude"):
            # Anthropic API
            # client = Anthropic()
            # response = client.messages.create(...)
            pass
        
        elif model_name.startswith("llama"):
            # Together.ai or local inference
            pass
        
        # Placeholder
        return f"[Model {model_name} response to: {prompt[:50]}...]"
    
    def extract_answer(self, text: str) -> str:
        """从模型输出中提取最终答案"""
        # 常见模式：
        # "The answer is X"
        # "Therefore, X"
        # "答案是 X"
        # 数字或数学表达式
        
        patterns = [
            r"(?:answer is|答案是|therefore|因此)[:\s]+([^\n\.]+)",
            r"(?:final answer|最终答案)[:\s]+([^\n\.]+)",
            r"\\boxed\{([^}]+)\}",  # LaTeX boxed
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # 如果没有匹配，尝试提取最后一行的数字
        lines = text.strip().split('\n')
        for line in reversed(lines):
            numbers = re.findall(r'-?\d+\.?\d*', line)
            if numbers:
                return numbers[-1]
        
        return ""
    
    def check_correctness(self, extracted: str, ground_truth: str) -> bool:
        """检查答案是否正确"""
        # 简单的字符串匹配
        # TODO: 实现更鲁棒的数值/符号比较
        extracted = extracted.strip().lower()
        ground_truth = ground_truth.strip().lower()
        
        # 移除空格
        extracted = extracted.replace(" ", "")
        ground_truth = ground_truth.replace(" ", "")
        
        return extracted == ground_truth
    
    def classify_solution_type(self, solution_text: str, problem: Problem) -> str:
        """
        分类解答类型
        
        Returns: "elegant", "brute-force", "hybrid", "invalid"
        """
        # TODO: 实现基于关键词/模式的分类
        # 或者使用GPT-4作为分类器
        
        # Elegant indicators:
        elegant_keywords = [
            "substitution", "symmetry", "geometric", "insight",
            "observe that", "notice that", "key insight",
            "变量替换", "对称", "几何", "洞察", "注意到"
        ]
        
        # Brute-force indicators:
        brute_keywords = [
            "expand", "solve for", "substitute", "compute",
            "calculate", "derivative", "lagrange multiplier",
            "展开", "求解", "计算", "代入", "拉格朗日"
        ]
        
        elegant_count = sum(1 for kw in elegant_keywords if kw in solution_text.lower())
        brute_count = sum(1 for kw in brute_keywords if kw in solution_text.lower())
        
        if elegant_count > brute_count * 1.5:
            return "elegant"
        elif brute_count > elegant_count * 1.5:
            return "brute-force"
        elif elegant_count > 0 and brute_count > 0:
            return "hybrid"
        else:
            return "invalid"
    
    def count_steps(self, solution_text: str) -> int:
        """统计解题步骤数"""
        # 简单方法：统计"Step", "步骤", 或数字标号
        step_patterns = [
            r'(?:Step|步骤)\s*\d+',
            r'^\d+[\.)]\s',  # 1. 或 1)
        ]
        
        step_count = 0
        for pattern in step_patterns:
            step_count += len(re.findall(pattern, solution_text, re.MULTILINE))
        
        # 如果没有明显标记，估计为段落数
        if step_count == 0:
            paragraphs = [p for p in solution_text.split('\n\n') if p.strip()]
            step_count = len(paragraphs)
        
        return max(1, step_count)  # 至少1步
    
    def calculate_elegance_score(self, solution: Solution, problem: Problem) -> float:
        """
        计算优雅度分数
        
        Score = α * (1/steps) + β * insight_bonus + γ * correctness
        """
        alpha, beta, gamma = 0.3, 0.5, 0.2
        
        # Step efficiency
        step_score = 1.0 / max(solution.step_count, 1)
        
        # Insight bonus
        insight_bonus = 1.0 if solution.solution_type == "elegant" else \
                       0.5 if solution.solution_type == "hybrid" else 0.0
        
        # Correctness
        correctness = 1.0 if solution.is_correct else 0.0
        
        return alpha * step_score + beta * insight_bonus + gamma * correctness
    
    def evaluate_single(self, problem: Problem, model_name: str, 
                       strategy: str = "zero_shot", n_samples: int = 1) -> List[Solution]:
        """评估单个问题"""
        solutions = []
        
        for i in range(n_samples):
            prompt = self.get_prompt(problem, strategy)
            raw_output = self.query_model(model_name, prompt)
            
            extracted = self.extract_answer(raw_output)
            is_correct = self.check_correctness(extracted, problem.answer)
            solution_type = self.classify_solution_type(raw_output, problem)
            step_count = self.count_steps(raw_output)
            
            solution = Solution(
                problem_id=problem.id,
                model_name=model_name,
                prompt_strategy=strategy,
                raw_output=raw_output,
                extracted_answer=extracted,
                is_correct=is_correct,
                solution_type=solution_type,
                step_count=step_count,
                elegance_score=0.0  # 待计算
            )
            
            solution.elegance_score = self.calculate_elegance_score(solution, problem)
            solutions.append(solution)
        
        return solutions
    
    def run_evaluation(self, models: List[str], strategies: List[str], 
                      n_samples: int = 5, output_file: str = "results.json"):
        """运行完整评估"""
        total = len(self.problems) * len(models) * len(strategies) * n_samples
        
        with tqdm(total=total, desc="Evaluating") as pbar:
            for problem in self.problems:
                for model in models:
                    for strategy in strategies:
                        solutions = self.evaluate_single(
                            problem, model, strategy, n_samples
                        )
                        self.results.extend(solutions)
                        pbar.update(n_samples)
        
        # 保存结果
        self.save_results(output_file)
    
    def save_results(self, filename: str):
        """保存评估结果"""
        results_dict = [
            {
                "problem_id": s.problem_id,
                "model": s.model_name,
                "strategy": s.prompt_strategy,
                "correct": s.is_correct,
                "solution_type": s.solution_type,
                "steps": s.step_count,
                "elegance": s.elegance_score,
                "answer": s.extracted_answer,
                "output": s.raw_output
            }
            for s in self.results
        ]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to {filename}")
    
    def analyze_results(self) -> Dict:
        """分析结果并生成统计"""
        import pandas as pd
        
        df = pd.DataFrame([
            {
                "model": s.model_name,
                "strategy": s.prompt_strategy,
                "correct": s.is_correct,
                "solution_type": s.solution_type,
                "elegance": s.elegance_score
            }
            for s in self.results
        ])
        
        # 按模型和策略分组
        analysis = {
            "overall_accuracy": df.groupby("model")["correct"].mean().to_dict(),
            "brute_force_rate": df.groupby("model")["solution_type"].apply(
                lambda x: (x == "brute-force").mean()
            ).to_dict(),
            "avg_elegance": df.groupby("model")["elegance"].mean().to_dict(),
            "strategy_effect": df.groupby(["model", "strategy"])["correct"].mean().to_dict()
        }
        
        return analysis


def main():
    """主函数示例"""
    
    # 初始化评估器
    evaluator = ERMRBenchmark(data_dir="./ermr_data")
    
    # 定义要评估的模型
    models = [
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "llama-2-7b",
        "llama-2-70b",
    ]
    
    # 定义prompting策略
    strategies = [
        "zero_shot",
        "strategy_hint",
        "one_shot_elegant",
        "cot"
    ]
    
    # 运行评估（每个配置5次采样）
    evaluator.run_evaluation(
        models=models,
        strategies=strategies,
        n_samples=5,
        output_file="ermr_results.json"
    )
    
    # 分析结果
    analysis = evaluator.analyze_results()
    
    # 保存分析结果
    with open("ermr_analysis.json", 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print("\n=== Evaluation Complete ===")
    print(f"Total evaluations: {len(evaluator.results)}")
    print(f"Overall accuracy: {sum(s.is_correct for s in evaluator.results) / len(evaluator.results):.2%}")


if __name__ == "__main__":
    main()
