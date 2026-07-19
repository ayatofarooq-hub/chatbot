# Offline Arabic Legal RAG Chatbot

This project uses JSON files as the only durable storage layer, Ollama for
local embeddings and answer generation, and ChromaDB as the generated search
index.

## Storage Layout

```text
data/
  legal_documents/       JSON legal records and uploaded normalized documents
  extracted_text/        extracted text JSON produced by document processing
  chunks.jsonl           generated chunks used for indexing
  citation_registry.json generated citation metadata
  metadata.json          settings, admin users, sessions, classifications, audit log
  chroma/                generated ChromaDB index
```

The legal document mapping preserves `id`, classification/category,
`law_number`, `year`, article references, title, summary, and source metadata
through retrieval and citation metadata.

## Setup

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull bge-m3
```

No external storage server is required.

## Build the Search Index

```powershell
python ingest_legal_documents.py
```

This reads JSON legal records from `data/legal_documents/` and the bundled
`dataset/` seed corpus, creates `data/chunks.jsonl`, writes
`data/citation_registry.json`, generates embeddings, and rebuilds the
`iraqi_legal_documents` collection in `data/chroma/`.

The same operation can be run with:

```powershell
python -m app.build_index
```

ChromaDB is generated from JSON files and can be rebuilt at any time.

## Run

Start the API and browser frontend:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

Supported routes include:

- `GET /health`
- `POST /ask`
- Settings, upload, and admin endpoints under `/api/...`

## Other Interfaces

```powershell
python app/rag_answer.py "اكتب سؤالك القانوني هنا"
python -m streamlit run app/ui.py
```

All interfaces share the same JSON document repository, retrieval, answer
generation, and citation validation logic.
