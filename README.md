# Offline Arabic Legal RAG Chatbot

This repository contains an offline Arabic legal RAG chatbot using Ollama,
ChromaDB, and Microsoft Word documents as its primary knowledge source.

## Knowledge Pipeline

```text
DOCX/TXT files
  -> modular document loaders
  -> Iraqi legal-aware chunks
  -> Ollama bge-m3 embeddings
  -> persistent ChromaDB collection
  -> hybrid semantic/lexical retrieval
  -> Ollama grounded answer generation
```

DOCX ingestion preserves, where available:

- document title and Word core properties;
- heading hierarchy and legal sections;
- article references such as `المادة 12`;
- tables in row order;
- Arabic Unicode text;
- source filename and source type.

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

Put one or more `.docx` or UTF-8 `.txt` files in
`data/legal_documents/`, then run:

```powershell
python ingest_legal_documents.py
```

This creates `data/chunks.jsonl`, generates embeddings, and rebuilds the
`iraqi_legal_documents` collection in `data/chroma/`.

The same pipeline can be run directly with:

```powershell
python -m app.build_index
```

See [docs/docx-ingestion-migration.md](docs/docx-ingestion-migration.md) for
the PDF-to-DOCX migration procedure and metadata details.

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

## Other Interfaces

```powershell
python app/rag_answer.py "اكتب سؤالك القانوني هنا"
python -m streamlit run app/ui.py
```

All interfaces share the same retrieval, answer generation, and citation
validation logic.
