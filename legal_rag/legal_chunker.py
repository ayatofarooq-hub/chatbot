"""Structure-first legal chunking for generated legal JSON."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .json_loader import LoadedLegalJson


MAX_CHUNK_CHARS = 1400
MIN_SPLIT_CHARS = 220
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.؟؛:])\s+|\n+")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _embedding_text(text: str, search_context: str) -> str:
    if not search_context:
        return text
    return f"{search_context}\n\n{text}".strip()


def _reference_numbers(references: list[dict[str, Any]], *types: str) -> str:
    allowed_types = set(types)
    values = [
        _text(reference.get("text"))
        for reference in references
        if isinstance(reference, dict)
        and _text(reference.get("text"))
        and (not allowed_types or _text(reference.get("type")) in allowed_types)
    ]
    return " | ".join(dict.fromkeys(values))


def _entity_values(value: Any) -> str:
    values: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_entity_values(item).split(" | "))
    elif isinstance(value, list):
        for item in value:
            values.extend(_entity_values(item).split(" | "))
    else:
        text = _text(value)
        if text:
            values.append(text)
    return " | ".join(dict.fromkeys(item for item in values if item))


def _base_metadata(document: LoadedLegalJson) -> dict[str, Any]:
    doc = document.document
    meta = document.metadata
    return {
        "document_id": document.document_id,
        "source_filename": document.source_file,
        "original_json_path": str(document.source_path),
        "json_path": str(document.source_path),
        "has_full_source_text": True,
        "has_full_document": True,
        "full_source_resolver": "original_json_long_text",
        "document_type": _text(doc.get("type") or meta.get("document_type")),
        "decision_number": _text(doc.get("decision_number") or meta.get("decision_number")),
        "document_number": _text(meta.get("document_number")),
        "law_number": _text(meta.get("law_number")),
        "year": _text(doc.get("year") or meta.get("year")),
        "law_year": _text(doc.get("year") or meta.get("year")),
        "issue_date": _text(doc.get("issue_date") or meta.get("issue_date")),
        "session_number": _text(doc.get("session_number") or meta.get("session_number")),
        "session_date": _text(doc.get("session_date") or meta.get("session_date")),
        "title": _text(doc.get("title") or meta.get("title")),
        "document_title": _text(doc.get("title") or meta.get("title")),
        "subject": _text(meta.get("subject")),
        "source_file": document.source_file,
        "source_type": "legal_document_parser_json",
        "reference_numbers": _reference_numbers(document.references),
        "recommendation_numbers": _reference_numbers(document.references, "recommendation_number"),
        "document_reference_numbers": _reference_numbers(document.references, "document_number", "reference_number"),
        "entities": _entity_values(document.entities),
        "page_number": 1,
    }


def _chunk_id(document_id: str, label: str, index: int) -> str:
    digest = hashlib.sha1(f"{document_id}|{label}|{index}".encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"{document_id}_{label}_{index}_{digest}"


def _paragraph_map(document: LoadedLegalJson) -> dict[int, str]:
    result: dict[int, str] = {}
    for paragraph in document.paragraphs:
        if not isinstance(paragraph, dict):
            continue
        try:
            index = int(paragraph.get("index"))
        except (TypeError, ValueError):
            continue
        text = _text(paragraph.get("text"))
        if text:
            result[index] = text
    return result


def _covered_paragraph_indexes(chunks: list[dict[str, Any]]) -> set[int]:
    covered: set[int] = set()
    for chunk in chunks:
        for value in re.findall(r"\d+", _text(chunk.get("paragraph_indexes"))):
            try:
                covered.add(int(value))
            except ValueError:
                continue
    return covered


def _split_large_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split only when needed, preferring sentence boundaries."""

    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    parts: list[str] = []
    current = ""
    for fragment in [part.strip() for part in SENTENCE_BOUNDARY_RE.split(text) if part.strip()]:
        candidate = "\n".join(part for part in (current, fragment) if part)
        if len(candidate) <= max_chars or len(current) < MIN_SPLIT_CHARS:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = fragment
    if current:
        parts.append(current)
    return parts


def _item_spans(document: LoadedLegalJson, paragraph_by_index: dict[int, str]) -> list[dict[str, Any]]:
    items = [
        item
        for item in document.legal_items
        if isinstance(item, dict) and item.get("kind") == "ordinal_item"
    ]
    items.sort(key=lambda item: int(item.get("paragraph_index") or 0))
    if not items:
        return []

    max_paragraph = max(paragraph_by_index) if paragraph_by_index else 0
    signature_start = min(
        (
            min(section.get("paragraph_indexes") or [])
            for section in document.sections
            if isinstance(section, dict)
            and section.get("section_id") == "signature"
            and section.get("paragraph_indexes")
        ),
        default=max_paragraph + 1,
    )

    spans: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        start = int(item.get("paragraph_index") or 0)
        next_start = (
            int(items[index + 1].get("paragraph_index") or 0)
            if index + 1 < len(items)
            else signature_start
        )
        end = max(start, next_start - 1)
        paragraphs = [
            paragraph_by_index[position]
            for position in range(start, end + 1)
            if paragraph_by_index.get(position)
        ]
        text = "\n".join(paragraphs).strip()
        if text:
            spans.append(
                {
                    "section": _text(item.get("number")),
                    "item_number": _text(item.get("number")),
                    "paragraph_indexes": list(range(start, end + 1)),
                    "text": text,
                }
            )
    return spans


def build_legal_chunks(document: LoadedLegalJson, max_chars: int = MAX_CHUNK_CHARS) -> list[dict[str, Any]]:
    """Build Chroma-ready chunks derived from long_text without rewriting it."""

    base = _base_metadata(document)
    search_context = document.search_record.search_text
    paragraph_by_index = _paragraph_map(document)
    chunks: list[dict[str, Any]] = []

    item_spans = _item_spans(document, paragraph_by_index)
    if item_spans:
        for item_index, span in enumerate(item_spans, start=1):
            for part_index, part in enumerate(_split_large_text(span["text"], max_chars=max_chars), start=1):
                chunk_index = len(chunks)
                chunk_id = _chunk_id(document.document_id, f"item_{item_index}", part_index)
                metadata = {
                    **base,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "section": span["section"],
                    "section_title": span["section"],
                    "item_number": span["item_number"],
                    "article_reference": span["item_number"],
                    "legal_reference": span["item_number"],
                    "paragraph_indexes": ",".join(str(value) for value in span["paragraph_indexes"]),
                }
                chunks.append(
                    {
                        "id": chunk_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "text": part,
                        "embedding_text": _embedding_text(part, search_context),
                        **metadata,
                        "metadata": metadata,
                    }
                )
    else:
        for section_index, section in enumerate(document.sections, start=1):
            section_text = _text(section.get("text") if isinstance(section, dict) else "")
            if not section_text:
                continue
            section_title = _text(section.get("title") or section.get("section_id"))
            for part_index, part in enumerate(_split_large_text(section_text, max_chars=max_chars), start=1):
                chunk_index = len(chunks)
                chunk_id = _chunk_id(document.document_id, f"section_{section_index}", part_index)
                metadata = {
                    **base,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "section": section_title,
                    "section_title": section_title,
                    "item_number": "",
                    "article_reference": section_title,
                    "legal_reference": section_title,
                    "paragraph_indexes": ",".join(str(value) for value in section.get("paragraph_indexes") or []),
                }
                chunks.append(
                    {
                        "id": chunk_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "text": part,
                        "embedding_text": _embedding_text(part, search_context),
                        **metadata,
                        "metadata": metadata,
                    }
                )

    if not chunks:
        for paragraph_index, paragraph_text in paragraph_by_index.items():
            for part_index, part in enumerate(_split_large_text(paragraph_text, max_chars=max_chars), start=1):
                chunk_index = len(chunks)
                chunk_id = _chunk_id(document.document_id, f"paragraph_{paragraph_index}", part_index)
                metadata = {
                    **base,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "section": "paragraph",
                    "section_title": "paragraph",
                    "item_number": "",
                    "article_reference": "",
                    "legal_reference": "paragraph",
                    "paragraph_indexes": str(paragraph_index),
                }
                chunks.append(
                    {
                        "id": chunk_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "text": part,
                        "embedding_text": _embedding_text(part, search_context),
                        **metadata,
                        "metadata": metadata,
                    }
                )

    covered_indexes = _covered_paragraph_indexes(chunks)
    uncovered_paragraphs = [
        (paragraph_index, paragraph_text)
        for paragraph_index, paragraph_text in paragraph_by_index.items()
        if paragraph_index not in covered_indexes
    ]
    for paragraph_index, paragraph_text in uncovered_paragraphs:
        for part_index, part in enumerate(_split_large_text(paragraph_text, max_chars=max_chars), start=1):
            chunk_index = len(chunks)
            chunk_id = _chunk_id(document.document_id, f"paragraph_{paragraph_index}", part_index)
            metadata = {
                **base,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "section": "paragraph",
                "section_title": "paragraph",
                "item_number": "",
                "article_reference": "",
                "legal_reference": "paragraph",
                "paragraph_indexes": str(paragraph_index),
            }
            chunks.append(
                {
                    "id": chunk_id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_index,
                    "text": part,
                    "embedding_text": _embedding_text(part, search_context),
                    **metadata,
                    "metadata": metadata,
                }
            )

    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
        chunk["total_chunks"] = len(chunks)
        chunk["metadata"]["chunk_index"] = index
        chunk["metadata"]["total_chunks"] = len(chunks)
    return chunks


def build_chunks_from_documents(documents: list[LoadedLegalJson], max_chars: int = MAX_CHUNK_CHARS) -> list[dict[str, Any]]:
    """Build chunks for every generated legal JSON document."""

    chunks: list[dict[str, Any]] = []
    for document in documents:
        chunks.extend(build_legal_chunks(document, max_chars=max_chars))
    return chunks
