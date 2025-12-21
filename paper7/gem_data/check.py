from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os

app = Flask(__name__)

# The directory where parsed PDF JSON files are stored.
PDF_PARSED_DIR = os.path.join(os.path.dirname(__file__), 'pdf_parsed')
# The file to save data that is correct but not elegant.
OUTPUT_DATA_FILE = os.path.join(os.path.dirname(__file__), 'gem_data/data.json')

@app.route('/')
def index():
    """
    Displays a list of JSON files from the pdf_parsed directory that can be reviewed.
    Only files with '__' in their name are considered for review.
    """
    try:
        files = [f for f in os.listdir(PDF_PARSED_DIR) if f.count('_') == 2 and f.endswith('.json')]
        return render_template('index.html', files=files)
    except FileNotFoundError:
        return "Error: The 'pdf_parsed' directory was not found.", 404


@app.route('/view/<filename>')
def view_file(filename):
    """Redirects to the first item in the file for review."""
    return redirect(url_for('view_item', filename=filename, item_index=0))


@app.route('/view/<filename>/<int:item_index>')
def view_item(filename, item_index):
    """Displays a single problem for review."""
    file_path = os.path.join(PDF_PARSED_DIR, filename)
    try:
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line.strip()))

        if item_index >= len(data):
            # All items have been reviewed, go back to the main index
            return redirect(url_for('index'))

        item = data[item_index]
        total_items = len(data)

        # $...$ --> \\(...\\) for better HTML rendering
        answer = item["answer"]
        left_delim = 0 # 0 for left, 1 for right
        new_answer = ""
        while "$" in answer:
            s1, s2 = answer.split("$", 1)
            if left_delim == 0:
                new_answer += s1 + "\\("
                left_delim = 1
            else:
                new_answer += s1 + "\\)"
                left_delim = 0
            answer = s2
        new_answer += answer
        item["answer"] = new_answer.replace("\n", "<br>")
        item["have_elegant_solution"] = False
        item["llm_answer"] = item["llm_answer"].replace("\n", "<br>")
                    
        return render_template('check.html', item=item, filename=filename, item_index=item_index, total_items=total_items)

    except FileNotFoundError:
        return f"Error: File '{filename}' not found.", 404
    except (json.JSONDecodeError, IndexError):
        return f"Error: Could not process file '{filename}'. It might be empty, malformed, or the index is out of bounds.", 500



@app.route('/save', methods=['POST'])
def save_judgement():
    """
    Saves the judgement for a single item and redirects to the next one.
    """
    form_data = request.form
    filename = form_data.get('filename')
    item_index = int(form_data.get('item_index', 0))
    
    if not filename:
        return "Error: Missing filename in form submission.", 400

    is_correct = form_data.get('correct') == 'true'
    have_elegant_solution = form_data.get('have') == 'true'
    is_similar = form_data.get('similar') == 'true'

    if have_elegant_solution:
        file_path = os.path.join(PDF_PARSED_DIR, filename)
        line = open(file_path, 'r', encoding='utf-8').readlines()[item_index]
        item = json.loads(line.strip())
            
        item['llm_answer_is_true'] = is_correct
        item['llm_answer_is_elegant'] = is_similar

        with open(OUTPUT_DATA_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
    # Redirect to the next item
    return redirect(url_for('view_item', filename=filename, item_index=item_index + 1))

if __name__ == '__main__':
    app.run(debug=True)