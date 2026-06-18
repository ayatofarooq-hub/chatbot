# DOCX Knowledge Ingestion Migration

## What Changed

The primary batch knowledge source is now `data/legal_documents/`.

- `.docx` files are parsed with `python-docx`.
- `.txt` files remain supported through the same loader registry.
- PDF extraction and `PyMuPDF` are no longer part of the active pipeline.
- Word paragraphs and tables are processed in their original document order.
- Word title, headings, article numbers, legal sections, tables, and core
  properties are retained where available.

The chatbot API routes, Ollama models, answer generation, and business logic
are unchanged.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Migrate Existing Knowledge

1. Export or convert each source legal document to `.docx`.
2. Review the Word styles. Use `Title` and `Heading 1` through `Heading 9`
   where possible.
3. Keep article labels in forms such as `المادة 12` or `مادة (١٢)`.
4. Put all `.docx` files in `data/legal_documents/`.
5. Rebuild the collection:

   ```powershell
   python ingest_legal_documents.py
   ```

The command batch-loads every supported document, writes inspectable chunks to
`data/chunks.jsonl`, generates Ollama embeddings, and replaces the
`iraqi_legal_documents` Chroma collection only after embedding succeeds.

## Metadata

Each Chroma record retains the existing compatibility fields:

- `source_file`
- `page_number`
- `chunk_index`

It also stores structured fields when available:

- `source_type`
- `document_title`
- `section_title`
- `article_reference`
- `section_reference`
- `legal_reference`
- `block_type`
- Word core properties prefixed with `document_`

DOCX does not expose reliable rendered page numbers because pagination depends
on Word layout. DOCX chunks therefore use page `1` for compatibility, while
`legal_reference` is the preferred locator.

## TXT And Future PDF Support

UTF-8 `.txt` files can be placed in the same folder. Legacy
`--- PAGE N ---` markers are still recognized.

Future PDF support should be added as another `DocumentLoader` implementation
and registered in `app/document_loaders.py`; no chunking or Chroma changes are
required.

## Rollback

Keep a backup of `data/chroma/` before rebuilding if the previous index must
remain available. Source files and the local Chroma database are ignored by
Git.
