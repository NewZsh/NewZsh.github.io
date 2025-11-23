import os
from scrapy import scrape_pdfs
from parse import parse_pdfs
from sol import solve_questions
from filter import filter_elegant_problems

# GEM (General Elegant Mathematics) Data Pipeline
# 
# This pipeline constructs the GEM dataset by identifying problems where:
# 1. An elegant solution exists (from ground truth).
# 2. Large Language Models (LLMs) tend to use brute-force approaches.
#
# Pipeline Steps:
# 1. scrapy.py:  Scrape PDF papers from https://aam.oajrc.org/
# 2. parse.py:   Parse PDFs to extract math problems into JSON format.
#                Keys: question, answer, final_answer (empty for proofs), sol_hint (insight)
# 3. sol.py:     LLM solves the questions to generate 'answer_llm' and 'final_answer_llm'.
# 4. filter.py:  Filter for problems where:
#                - LLM result is correct (final_answer_llm == final_answer)
#                - LLM method is brute-force/complex vs. the elegant ground truth.
#
# The resulting dataset highlights the "Elegance Gap".

def main():
    # Configuration
    PDF_DIR = "pdf_raw"
    RAW_PROBLEMS_FILE = "problems.json"
    LLM_RESULTS_FILE = "problems_with_llm.json"
    GEM_DATASET_FILE = "gem_data.json"

    print("=== Starting GEM Data Pipeline ===")

    # Step 1: Scrape
    print("\n[Step 1] Scraping PDFs...")
    scrape_pdfs(output_dir=PDF_DIR)

    # Step 2: Parse
    print("\n[Step 2] Parsing PDFs...")
    parse_pdfs(pdf_dir=PDF_DIR, output_file=RAW_PROBLEMS_FILE)

    # Step 3: Solve with LLM
    print("\n[Step 3] Solving with LLM...")
    solve_questions(input_file=RAW_PROBLEMS_FILE, output_file=LLM_RESULTS_FILE)

    # Step 4: Filter for Elegance
    print("\n[Step 4] Filtering for GEM dataset...")
    filter_elegant_problems(input_file=LLM_RESULTS_FILE, output_file=GEM_DATASET_FILE)

    print("\n=== GEM Pipeline Completed ===")
    print(f"Final dataset saved to {GEM_DATASET_FILE}")

if __name__ == "__main__":
    main()
