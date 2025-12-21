# GEM 数据处理流程

该目录包含用于从PDF文档中提取、处理和验证数学问题数据的脚本。

## 工作流

数据处理流程主要分为以下几个步骤：

1.  **解析 (parse.py)**:
    -   **功能**: 从 `pdf_raw/` 目录下的 PDF 文件中提取数学问题。
    -   **过程**: 使用 `vlm_gemini.py` 中的函数调用 Gemini Pro Vision API，将 PDF 文件发送给模型，并根据特定提示词提取问题、答案、解题思路等信息。
    -   **输出**: 提取出的问题以 JSONL 格式保存在 `pdf_parsed/` 目录下。

2.  **求解 (sol.py)**:
    -   **功能**: 使用大型语言模型（LLM）为 `parse.py` 提取出的问题生成解答。
    -   **过程**: 读取解析后的问题文件，调用 `llm.py` 封装的 LLM API（如豆包1.5）为每个问题生成详细的解题步骤。
    -   **输出**: 将原始问题、LLM 生成的答案以及两个验证标签（`llm_answer_is_true` 和 `llm_answer_is_elegant`）一同保存到一个新的 JSONL 文件中。

3.  **人工校验 (check.py)**:
    -   **功能**: 提供一个 Web 界面，用于人工审核和标注数据。
    -   **过程**: 这是一个 Flask 应用，允许用户逐条查看问题、原始答案和 LLM 生成的答案。
        -   用户可以选择 "Is AI solution correct?" 或 "Is the reasoning similar (elegant)?" 来标注 LLM 答案的正确性和优雅性。
        -   勾选 "Does the question have an elegant solution?" 后，当前数据将被保存到 `gem_data/data.json` 文件中。
        -   审核要点1：LLM 做对与否和该问题是否存在优雅解法是两个独立的维度。所以要人工重点判断该题是否存在暴力解法和优雅解法两种。
        -   审核要点2：Answer字段是爬取的，Hint也是，所以不太可能存在错误，人工判断AI solution的对错和优雅性可以快速对照Answer和Hint来判断，不需要逐字核验AI solution。
    -   **输出**: 审核通过的数据将被保存到 `gem_data/data.json` 文件中。