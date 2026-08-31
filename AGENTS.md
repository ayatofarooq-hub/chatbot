# AGENTS

This project is an offline Arabic legal RAG chatbot.
The durable legal knowledge source is PostgreSQL `public.iraqi_laws`; ChromaDB is generated from that source and must not be edited directly.

## Key points for AI coding agents

- Python 3.10+ backend.
- Main entrypoints:
  - `app/api.py` - HTTP API, static frontend serving, `/ask` answer flow.
  - `app/build_index.py` - rebuilds the ChromaDB vector index from legal documents.
  - `app/rag_answer.py` - answer generation and citation handling.
  - `app/search_index.py` - semantic/BM25 retrieval.
  - `app/runtime_settings.py` - runtime configuration for models, upload limits, and retrieval.
- `app/prompts.py` contains the Arabic legal prompt used by answer generation.
- `backend/services` contains helper services for documents, embeddings, and JSON repository access.

## Recommended workflows

- Setup environment:
  - `python -m venv .venv`
  - `.venv\Scripts\Activate.ps1`
  - `python -m pip install -r requirements.txt`
- Configure database:
  - `Copy-Item .env.example .env`
  - edit `.env`, set `DATABASE_URL`
  - `python -m app.database`
- Build the search index:
  - `python ingest_legal_documents.py`
  - or `python -m app.build_index`
- Run the API:
  - `python -m uvicorn app.api:app --host 127.0.0.1 --port 8000`
- Run the UI:
  - `python -m streamlit run app/ui.py`

## Constraints and conventions

- The legal model must only answer from retrieved context and citations backed by `citation_registry.json`.
- Do not manually edit generated files under `data/chroma` or `data/citation_registry.json`.
- Use `runtime_settings()` for any runtime-configurable values.
- Preserve the retrieval+generation separation: query -> search -> registry validation -> `generate_answer()`.
- Tests use `unittest` and `unittest.mock.patch` in `tests/`.

## References

- `README.md` - primary setup and architecture.
- `docs/settings.md` - runtime settings documentation.
