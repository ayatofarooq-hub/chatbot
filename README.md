# Offline Arabic Legal RAG Chatbot

This repository contains an offline Arabic legal retrieval-augmented
generation (RAG) chatbot with terminal, browser, API, and Streamlit
interfaces.

## Project Structure

```text
offline-legal-chatbot/
├── app/
│   ├── __init__.py
│   ├── build_index.py
│   ├── chunk_text.py
│   ├── config.py
│   ├── extract_pdfs.py
│   ├── test_ollama.py
│   ├── text_cleaning.py
│   └── main.py
├── data/
│   ├── raw_pdfs/
│   ├── extracted_text/
│   └── chroma/
├── tests/
├── .gitignore
├── README.md
└── requirements.txt
```

- `app/config.py` stores project paths and local model names.
- `app/extract_pdfs.py` extracts text from each PDF page without OCR.
- `app/chunk_text.py` creates page-aware legal text chunks.
- `app/build_index.py` embeds chunks and stores them in persistent ChromaDB.
- `app/main.py` is a temporary setup check, not a chatbot.
- `data/raw_pdfs/` contains the Arabic legal PDF files.
- `data/extracted_text/` will contain text extracted from the PDFs.
- `data/chroma/` will contain the local Chroma vector database.

## Default Models

The future project is configured to use local Ollama models:

- Chat model: `qwen2.5:7b`
- Embedding model: `bge-m3`

## Setup

Python 3.10 or newer is recommended.

1. Open a terminal in the project directory:

   ```bash
   cd offline-legal-chatbot
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, activate it with:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. Install the Python dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Install and start Ollama, then download the configured models:

   ```bash
   ollama pull qwen2.5:7b
   ollama pull bge-m3
   ```

5. Put legal PDF files in `data/raw_pdfs/`.

## Run the Initial Setup Check

The current entry point only creates missing data folders and prints the
configuration:

```bash
python -m app.main
```

In a later stage, this command can start the chatbot after the RAG pipeline
and interface are implemented.

## Extract Text from PDFs

Place PDF files in `data/raw_pdfs/`, then run:

```bash
python app/extract_pdfs.py
```

The script creates one UTF-8 `.txt` file per PDF in `data/extracted_text/`.
Each output file includes page separators such as `--- PAGE 1 ---`. This step
extracts existing PDF text only and does not use OCR or ChromaDB.

## Build the Vector Index

After extracting and chunking the legal documents, make sure Ollama is running
and the `bge-m3` model is installed. Then run:

```bash
python app/build_index.py
```

This command recreates the `iraqi_legal_documents` collection in
`data/chroma/`, generates embeddings with the configured Ollama embedding
model, and stores each chunk with its source file, page number, and chunk
index. It does not call the chat model.

## Ask Questions

Run one question from the terminal:

```powershell
python app/rag_answer.py "اكتب سؤالك القانوني هنا"
```

Start the API and primary browser interface:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`. The standalone browser frontend is the
primary interface and is served by the same Starlette process as the API.

The Streamlit implementation remains available as a fallback:

```powershell
python -m streamlit run app/ui.py
```

Send a `POST` request to `http://127.0.0.1:8000/ask` with:

```json
{
  "question": "ما هي عقوبة جريمة الإرهاب في القانون العراقي؟",
  "include_snippets": true
}
```

Use `GET http://127.0.0.1:8000/health` to check that the API process is
running. Ollama must also be running, and the Chroma index must already exist.

Manage indexed text documents with these endpoints:

- `GET /documents` lists documents.
- `POST /documents` inserts a document.
- `PUT /documents/{filename}` replaces a document.
- `DELETE /documents/{filename}` deletes a document.

Insert request:

```json
{
  "filename": "new-law.txt",
  "content": "--- PAGE 1 ---\nThe legal text for page one."
}
```

Update requests use the same `content` field. Plain text without page markers
is automatically stored as page 1. These endpoints update both
`data/extracted_text` and the Chroma collection; Ollama must be available to
embed inserted or updated content.

All interfaces use the same retrieval, answer generation, correction, and
citation-vetting flow. If the model answer still fails citation vetting after
the correction attempt, the answer remains visible and the validation
warnings are shown below it.

## Further Development

Possible future work includes:

1. OCR support for scanned PDFs.
2. Retrieval quality evaluation.
3. Automated answer-grounding benchmarks.

This project is intended for local development. Legal documents, extracted
text, and vector database files are excluded from Git.
