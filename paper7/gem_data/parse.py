import json
import os

def parse_pdfs(pdf_dir="pdf_raw", output_file="problems.json"):
    """
    Parses PDFs to extract math problems and saves to JSON.
    Keys: question, answer, final_answer, sol_hint
    """
    print(f"Parsing PDFs from {pdf_dir}...")
    
    problems = []
    
    # Placeholder for PDF parsing logic
    # In a real implementation, we would:
    # 1. Iterate over PDF files in pdf_dir
    # 2. Use a library like PyPDF2 or pdfminer to extract text
    # 3. Use regex or LLM to extract problem components
    
    # Example structure
    # problems.append({
    #     "id": "1",
    #     "question": "...",
    #     "answer": "...", # Full solution
    #     "final_answer": "...", # The result
    #     "sol_hint": "..." # Hint/Insight
    #     "question_img_ggb": "...", # optional, if the problem has a img, draw with geogebra language
    # })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(problems, f, indent=2, ensure_ascii=False)
        
    print(f"Parsing completed. {len(problems)} problems saved to {output_file}")

if __name__ == "__main__":
    parse_pdfs()
