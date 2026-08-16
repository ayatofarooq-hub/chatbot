# Parser App / Chatbot Integration Contract

Status: contract only. No integration is implemented in this phase.

## Independence

The parser app and chatbot remain completely independent applications.

- The parser app does not import chatbot modules.
- The parser app does not call chatbot routes.
- The parser app does not use chatbot authentication.
- The parser app does not use chatbot storage, ChromaDB, embeddings, retrieval, chunking, or frontend code.
- The chatbot is not required to run the parser.
- The parser is not required to run the chatbot.

## Parser Guarantees

The parser guarantees:

- Every approved document produces one JSON file.
- Every JSON follows the agreed standard schema: `iraqi_legal_document.v1`.
- Every JSON is UTF-8 encoded.
- Every JSON is self-contained.
- Every JSON can be consumed without additional preprocessing.
- Every JSON is written under `parser_app/data/output/` unless the CLI caller explicitly provides another output directory.
- Parser-generated JSON contains no ChromaDB fields, embedding fields, vector fields, retrieval fields, chunk IDs, collection names, scores, or distances.

## Chatbot Guarantees

The chatbot guarantees:

- It only reads JSON files from the parser output.
- It never parses DOCX, PDF, TXT, RTF, HTML, or Markdown source files directly.
- It never modifies parser-generated JSON.
- It performs chunking, embeddings, indexing, and retrieval using only parser-generated JSON output.
- It treats parser-generated JSON as immutable input.

## Agreed JSON Schema

Every parser JSON file uses exactly these top-level keys:

```text
schema_version
created_at
source
metadata
document_type
legal_content
model_analysis
extraction
```

Schema version:

```text
iraqi_legal_document.v1
```

## Handoff Boundary

The only contract boundary is the filesystem JSON output.

```text
parser_app/data/output/*.json
```

No Python imports, in-process calls, database coupling, shared state, or shared utility modules are part of this contract.
