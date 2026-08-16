# Parser App

Standalone document parser application for converting source documents into structured JSON.

This project is intentionally independent from the chatbot application in `app/`.

## Boundaries

- Do not import from `app`.
- Do not import chatbot modules.
- Do not import ChromaDB.
- Do not import API routes, authentication, chat history, frontend code, or shared chatbot utilities.
- Keep parser-specific code inside `parser_app`.

## Layout

```text
parser_app/
  config.py
  main.py
  loaders/
  cleaners/
  extractors/
  prompts/
  validators/
  builders/
  exporters/
  models/
  utils/
  data/
    input/
    output/
    logs/
```

## Setup

```powershell
cd parser_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Pipeline

The parser runs as an independent pipeline:

```text
Load Document
  -> Clean Document
  -> Detect Iraqi Government Document Type
  -> Extract Metadata
  -> Extract Legal Content
  -> Build JSON
  -> Validate JSON
  -> Save JSON
```

Each step is implemented as a separate component and passes explicit Python
objects defined in `models/document.py`.

The generic loader supports:

- DOCX
- PDF
- TXT
- RTF
- HTML
- Markdown

The loader only reads files and returns structured text:

```python
Document(
    filename,
    extension,
    pages,
    paragraphs,
    tables,
    raw_text,
)
```

The Iraqi government detector uses rule-based classification first. An optional
LLM classifier can be injected later, but it is only called when rules are below
the configured confidence threshold.

The metadata extraction engine is deterministic. It extracts structured fields
from labels, dates, section markers, and known document phrases without calling
an LLM. Missing fields are left as `null` or empty lists.

The text cleaning engine normalizes documents while preserving legal meaning.
It removes duplicated headers, duplicated footers, page counters, footer stamps,
and excessive whitespace. It does not summarize, paraphrase, or rewrite the
document, and it preserves headings, numbering, bullet points, legal references,
monetary values, and article numbers.

## Local Qwen Analysis

The parser can optionally call Qwen2.5-1.5B through the local Ollama server only.
The default model is `qwen2.5:1.5b` and the default host is
`http://127.0.0.1:11434`.

The model is used only as a parser component for:

- understanding legal meaning
- identifying legal entities
- generating structured fields
- creating summaries when requested
- producing JSON only

It must never answer questions and must never behave like a chatbot. The code
does not expose a chat or question-answering method.

## Legal Extraction

The legal extraction engine combines deterministic rules, extracted metadata,
and optional LLM fills. Rule-based and metadata-derived values always take
precedence. When `--use-llm` is enabled, Qwen is only asked for fields that are
still missing after deterministic extraction.

Extracted legal fields include:

- legal objective
- executive summary
- implementation responsibilities
- decision outcome
- legal references
- affected entities

Each generated field records its source in `legal_content.extraction_sources`.

## Standard JSON

Every processed document writes the same standalone Iraqi legal document schema,
regardless of original document type:

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

The schema version is `iraqi_legal_document.v1`. The output is only a legal
document representation. It must not contain ChromaDB fields, embedding fields,
vector fields, retrieval fields, chunk ids, collection names, scores, or
distances.

The non-integration boundary with the chatbot is defined in
`INTEGRATION_CONTRACT.md`. This is a contract only; the two applications remain
independent.

## Validation

Every generated JSON is validated before it is accepted. Validation checks:

- valid JSON
- UTF-8 readable output
- required standard fields
- duplicate sections
- missing core metadata
- invalid dates
- invalid empty numbering
- banned ChromaDB, embedding, vector, and retrieval fields

If validation fails, the parser retries extraction once for that document. If
the retry also fails, the error is logged to `parser_app/data/logs` and the
batch continues with the next document.

Each document is processed independently. A load, extraction, validation, or
export failure for one file is logged and does not stop the batch.

## Processing Logs

Detailed UTF-8 logs are written to `parser_app/data/logs`.

- `processing.log` records each stage for each filename:
  Loading document, Cleaning document, Detecting document type,
  Extracting metadata, Extracting legal content, Running Qwen, Building JSON,
  Validating JSON, Saving output, and Completed.
- `validation_errors.log` records validation and processing errors.

Errors include the filename and failed stage.

To enable model analysis:

```powershell
python main.py --use-llm
```

To disable summaries while keeping other model-generated structured fields:

```powershell
python main.py --use-llm --no-summary
```

## Usage

Place supported files in `parser_app/data/input`, then run:

```powershell
python main.py
```

JSON output is written to `parser_app/data/output`.

## Tests

Run parser-app tests from inside `parser_app`:

```powershell
python -m pytest -q
```

The tests use only parser_app modules and temporary files. They do not import
or depend on the chatbot.

You can also process a single local file:

```powershell
python main.py data/input/document.docx
```

Or pass multiple files/directories:

```powershell
python main.py data/input/document.docx data/input/other.pdf
```

To process an entire folder:

```powershell
python main.py input/
```

This writes one JSON per source file:

```text
input/document1.docx -> data/output/document1.json
input/document2.docx -> data/output/document2.json
input/document3.docx -> data/output/document3.json
```

By default, output filenames use the source document stem. The parser can also
generate legal-derived filenames:

```powershell
python main.py input/ --legal-filenames
```

Legal-derived filename format:

```text
<document_type>_<year>_<number>.json
```

When no reliable document or reference number exists, the parser uses a stable
short hash suffix so each JSON file remains independent and non-overwriting.
