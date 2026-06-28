# Offline Arabic Legal RAG Chatbot

This project uses PostgreSQL as its only legal knowledge source, Ollama for
local embeddings and answer generation, and ChromaDB as a generated search
index.

## Knowledge Pipeline

```text
PostgreSQL public.iraqi_laws
  -> legal metadata mapping and chunking
  -> Ollama bge-m3 embeddings
  -> persistent ChromaDB collection
  -> citation_registry.json
  -> hybrid semantic/BM25 retrieval
  -> Ollama grounded answer generation
```

The database mapping preserves `id`, `classification`, `law_number`,
`law_year`, `article_number`, `law_name`, and `summary` through retrieval and
citation metadata.

## Setup

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
ollama pull bge-m3
```

## PostgreSQL Configuration

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set the real application password:

```env
DATABASE_URL=postgresql+psycopg://chatbot_app:PASSWORD@localhost:5432/laws_iraqi
```

Test the connection:

```powershell
python -m app.database
```

The configured role must have `SELECT` access to
`public.iraqi_laws`.

## Build the Search Index

```powershell
python ingest_legal_documents.py
```

This reads every row from `public.iraqi_laws`, creates
`data/chunks.jsonl`, writes `data/citation_registry.json`, generates
embeddings, and rebuilds the `iraqi_legal_documents` collection in
`data/chroma/`.

The same operation can be run with:

```powershell
python -m app.build_index
```

PostgreSQL is the durable legal store. ChromaDB is generated and must not be
edited directly.

## Run

Start the API and browser frontend:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

Supported routes:

- `GET /health`
- `POST /ask`

Example request:

```json
{
  "question": "ما هي عقوبة هذه الجريمة؟",
  "include_snippets": true
}
```

`POST /ask` returns answers, warnings, PostgreSQL-backed citations, and
optional evidence snippets.

## Other Interfaces

```powershell
python app/rag_answer.py "اكتب سؤالك القانوني هنا"
python -m streamlit run app/ui.py
```

All interfaces share the same retrieval, answer generation, and citation
validation logic.
