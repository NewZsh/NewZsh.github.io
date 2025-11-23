import json

def filter_elegant_problems(input_file="problems_with_llm.json", output_file="gem_data.json"):
    """
    Filters problems where LLM used brute force (different method) but got correct result.
    Criteria:
    1. final_answer_llm == final_answer (Correct result)
    2. answer_llm is significantly different/longer than answer (Brute force vs Elegant)
    """
    print(f"Filtering problems from {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            problems = json.load(f)
    except FileNotFoundError:
        print(f"File {input_file} not found.")
        return

    gem_problems = []
    
    for problem in problems:
        final_answer = problem.get("final_answer")
        final_answer_llm = problem.get("final_answer_llm")
        
        # Check correctness
        if final_answer != final_answer_llm:
            continue
            
        # Check for "Elegance Gap"
        # In a real implementation, we might compare length or use an LLM to judge
        # if is_brute_force(problem["answer_llm"]) and is_elegant(problem["answer"]):
        #     gem_problems.append(problem)
        
        # For now, pass all correct ones as placeholder
        gem_problems.append(problem)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(gem_problems, f, indent=2, ensure_ascii=False)
        
    print(f"Filtering completed. {len(gem_problems)} GEM problems saved to {output_file}")

if __name__ == "__main__":
    filter_elegant_problems()
