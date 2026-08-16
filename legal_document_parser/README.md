# Legal Document Parser

Independent DOCX to JSON parser for Iraqi legal documents.

## Analysis Report

1. Existing chatbot architecture: `app/api.py` exposes the HTTP API and frontend routes, `app/rag_answer.py` generates answers, `app/search_index.py` retrieves context, and `frontend/` contains the browser UI. `LegalChatbotDesktop/` is a desktop wrapper.

2. Existing RAG architecture: JSON legal records are chunked by `app/chunk_text.py`, indexed by `app/build_index.py`, searched by `app/search_index.py`, and answered through `app/rag_answer.py`.

3. Existing document processing: `app/main.py`, `app/document_pipeline.py`, `app/uploaded_documents.py`, `backend/services/document_service.py`, and `parser_app/` contain existing DOCX/document logic. Some existing flows are coupled to Qwen/Ollama, ChromaDB, repository writes, or chatbot review/indexing.

4. Existing database/vector storage: durable legal records are JSON files under `data/legal_documents/`, seed JSON files under `dataset/`, metadata under `data/metadata.json`, chunks under `data/chunks.jsonl`, citation metadata under `data/citation_registry.json`, and ChromaDB under `data/chroma/`. No PostgreSQL is required by the current project.

5. Existing model configuration: `app/config.py` sets `CHAT_MODEL = qwen2.5:3b`, `DOCUMENT_INFO_MODEL = qwen2.5:1.5b`, and `EMBEDDING_MODEL = bge-m3`. Runtime model settings are used by chatbot/search code.

6. Files that must not be modified for this stage: `app/**`, `backend/**`, `frontend/**`, `data/**` except reading/copying provided DOCX input, `dataset/**`, `parser_app/**`, `scripts/**`, existing tests, ChromaDB files, and chatbot configuration.

7. Recommended independent parser directory: `legal_document_parser/`. This directory owns its input, output, parser modules, schema, tests, configuration, and README. It does not import the chatbot or older parser application.

## Boundary

This stage is only:

```text
DOCX -> Legal Document Parser -> Structured JSON with full long legal text
```

The parser does not use PostgreSQL, ChromaDB, Ollama, chatbot routes, chatbot APIs, chatbot database logic, or chatbot services.

## JSON Contract

Every generated JSON is UTF-8 and uses:

```text
schema_version: iraqi_legal_document.v2
```

Required top-level structure:

```json
{
  "schema_version": "iraqi_legal_document.v2",
  "source": {},
  "document": {},
  "metadata": {},
  "references": [],
  "decision": {
    "sections": []
  },
  "long_text": "",
  "body": "",
  "paragraphs": [],
  "legal_entities": {},
  "extracted_fields": {},
  "signature": {}
}
```

`long_text` is the complete legal source text extracted from the DOCX, including title, introduction, references, decision sections, numbered items, paragraphs, responsibilities, signature, and dates. It is not a summary and is not truncated.

`body` is also the complete document body and is kept equal to `long_text`, so no downstream consumer loses legal text. Structured fields are machine-readable extraction only and do not replace the full text.

Validation checks:

- valid JSON schema
- non-empty `long_text`
- non-empty `body`
- matching `body` and `long_text`
- paragraphs exist
- sections exist
- numbered items are represented when extracted
- extracted paragraphs, sections, and numbered items remain present in `long_text`
- UTF-8 Arabic output

## Layout

```text
legal_document_parser/
  input/docx/
  output/json/
  parser/
  schemas/legal_document_v2.json
  tests/
  config.py
  main.py
```

## Usage

Place `.docx` files in:

```text
legal_document_parser/input/docx/
```

Run:

```powershell
cd legal_document_parser
python main.py
```

Output is written as UTF-8 JSON:

```text
legal_document_parser/output/json/<filename>.json
```

Arabic text is preserved. Legal text is not summarized, truncated, or rewritten. Missing extracted fields are `null`.
