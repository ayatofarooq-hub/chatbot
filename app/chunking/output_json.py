"""Build Chroma-ready chunks from generated JSON payloads."""

import hashlib
import json
from pathlib import Path

from app.arabic_search import normalized_search_blob
from app.legal_source_text import source_text_from_payload


def first_value(values: object) -> str:
    """Return the first non-empty scalar value from a list-like value."""

    if isinstance(values, list):
        for value in values:
            text = str(value).strip()
            if text:
                return text
        return ""
    return str(values or "").strip()


def primary_document_text(payload: dict) -> str:
    """Return full text from supported parser JSON: long_text, then body."""

    return source_text_from_payload(payload)


def _flatten_values(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_flatten_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_flatten_values(item))
    else:
        text = str(value or "").strip()
        if text:
            values.append(text)
    return values


def _search_context(payload: dict) -> str:
    values: list[str] = []
    for key in ("title", "document_type", "metadata", "references", "legal_entities", "extracted_fields"):
        values.extend(_flatten_values(payload.get(key)))
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    values.extend(_flatten_values(document))
    values.extend(_flatten_values(source.get("parser")))
    raw_context = " | ".join(dict.fromkeys(value for value in values if value))[:1200]
    normalized_context = normalized_search_blob(raw_context)
    return "\n".join(
        dict.fromkeys(value for value in (raw_context, normalized_context) if value)
    )


def build_chunks_from_output_json(payload: dict) -> list[dict]:
    """Build Chroma-ready chunks from one generated JSON payload."""

    from app.chunk_text import split_text

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    source_file = str(payload.get("source_file") or source.get("filename") or "document")
    source_hash = hashlib.sha1(source_file.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    text = primary_document_text(payload)
    if not text:
        text = str(payload.get("summary") or payload.get("title") or "").strip()
    if not text:
        return []

    regex_metadata = payload.get("regex_metadata") or {}
    search_context = _search_context(payload)
    chunks = []
    for chunk_index, chunk_text in enumerate(split_text(text)):
        chunks.append(
            {
                "id": f"{source_hash}-chunk-{chunk_index}",
                "source_file": source_file,
                "source_type": "docx_json",
                "document_type": str(payload.get("document_type") or document.get("type") or ""),
                "document_title": str(payload.get("title") or document.get("title") or ""),
                "page_number": 1,
                "chunk_index": chunk_index,
                "section_title": "",
                "article_reference": first_value(regex_metadata.get("article_numbers")),
                "section_reference": "",
                "legal_reference": first_value(payload.get("legal_references")),
                "block_type": "paragraph",
                "text": chunk_text,
                "embedding_text": f"{search_context}\n\n{chunk_text}".strip() if search_context else chunk_text,
                "document_law_number": first_value(regex_metadata.get("law_numbers")),
                "document_law_year": first_value(regex_metadata.get("years")),
                "document_article_number": first_value(regex_metadata.get("article_numbers")),
            }
        )
    return chunks


def load_output_chunks(json_files: list[Path]) -> list[dict]:
    """Load generated JSON files and convert them to Chroma chunks."""

    chunks: list[dict] = []
    for json_file in json_files:
        payload = json.loads(json_file.read_text(encoding="utf-8-sig"))
        chunks.extend(build_chunks_from_output_json(payload))
    return chunks
