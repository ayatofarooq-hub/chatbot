# Offline Arabic Legal RAG Chatbot

This repository contains an offline Arabic legal RAG chatbot using Ollama,
ChromaDB, and Microsoft Word documents as its primary knowledge source.

## Knowledge Pipeline

```text
PDF/DOCX/TXT files
  -> modular document loaders
  -> Iraqi legal-aware chunks
  -> Ollama bge-m3 embeddings
  -> persistent ChromaDB collection
  -> citation_registry.json
  -> hybrid semantic/BM25 retrieval
  -> Ollama grounded answer generation
```

PDF, DOCX, and TXT ingestion preserve, where available:

- document title and Word core properties;
- heading hierarchy and legal sections;
- article references such as `المادة 12`;
- document classification as `قانون` or `قرار`;
- tables in row order;
- Arabic Unicode text;
- source filename and source type.

Classification uses Arabic regex signal scoring during ingestion. The resulting
`document_type` is stored in `data/chunks.jsonl`, Chroma metadata,
`data/citation_registry.json`, and `/ask` snippets/citations.

## Setup

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull bge-m3
```

## Batch Ingestion

Put one or more text-layer `.pdf`, `.docx`, or UTF-8 `.txt` files in
`data/legal_documents/`, then run:

```powershell
python ingest_legal_documents.py
```

This creates `data/chunks.jsonl`, writes `data/citation_registry.json`,
generates embeddings, and rebuilds the `iraqi_legal_documents` collection in
`data/chroma/`.

The same pipeline can be run directly with:

```powershell
python -m app.build_index
```

See [docs/docx-ingestion-migration.md](docs/docx-ingestion-migration.md) for
the PDF-to-DOCX migration procedure and metadata details.

## OCR For Scanned PDFs

PDF ingestion first uses the embedded text layer through `pdfplumber`. If a
PDF page has no usable text, the loader falls back to OCR with Tesseract:

- Python packages: `pypdfium2` and `pytesseract` from `requirements.txt`
- System program: Tesseract OCR installed on Windows and available on `PATH`
- Language data: Arabic trained data, used as `ara+eng`

If OCR dependencies or the Tesseract executable are missing, scanned PDF
ingestion fails with a setup error instead of indexing empty pages.

For best Arabic OCR results, scan at 300-400 DPI, keep pages straight, avoid
shadows, and prefer black text on a white background. The loader renders scanned
PDF pages at 400 DPI, tries multiple Tesseract layouts, and keeps the result
with the strongest Arabic/legal signal.

## Automatic Weekly Ingestion

For a long-running local watcher:

```powershell
python watch_legal_documents.py
```

For Windows Task Scheduler, run a periodic one-shot check:

```powershell
python watch_legal_documents.py --once
```

## Run

Start the API and browser frontend:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

The existing routes remain unchanged:

- `GET /health`
- `POST /ask`
- `GET /documents`
- `POST /documents`
- `PUT /documents/{filename}`
- `DELETE /documents/{filename}`

The document-management endpoints remain text-based for backward
compatibility. Batch DOCX ingestion is filesystem-based.

`POST /ask` returns registry-backed structured citations:

```json
{
  "answer": "...",
  "citations": [
    {
      "law": "قانون العقوبات رقم 111 لسنة 1969",
      "article": "المادة 405",
      "source_file": "penal_code.docx",
      "ingest_date": "2026-06-11",
      "chunk_id": "abc123"
    }
  ]
}
```

## Other Interfaces

```powershell
python app/rag_answer.py "اكتب سؤالك القانوني هنا"
python -m streamlit run app/ui.py
```

All interfaces share the same retrieval, answer generation, and citation
validation logic.
