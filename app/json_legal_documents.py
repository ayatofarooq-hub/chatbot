"""Map JSON-backed legal documents into the legal document pipeline."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

try:
    from .legal_document import DocumentBlock, LoadedDocument
    from .legal_source_text import source_text_from_payload
    from .text_encoding import repair_mojibake
    from backend.services.json_repository import JsonRepository
except ImportError:
    from legal_document import DocumentBlock, LoadedDocument
    from legal_source_text import source_text_from_payload
    from text_encoding import repair_mojibake
    from backend.services.json_repository import JsonRepository


def _text(value: Any) -> str:
    return "" if value is None else repair_mojibake(str(value)).strip()


SUMMARY_SECTION_LABELS = ("الشرح التفصيلي", "الشرح التفصيلى")
SUMMARY_SECTION_PATTERN = re.compile(
    r"^\s*(?:summary|ملخص|الملخص|الخلاصة|الشرح التفصيلي|الشرح التفصيلى)\s*[:：\-]?",
    re.IGNORECASE,
)


def _without_summary_sections(text: str) -> str:
    lines = [
        line
        for line in str(text or "").splitlines()
        if not SUMMARY_SECTION_PATTERN.match(line)
        and not any(label in line for label in SUMMARY_SECTION_LABELS)
    ]
    return _text("\n".join(lines))


def _primary_document_text(document: Mapping[str, Any]) -> str:
    return _without_summary_sections(source_text_from_payload(dict(document)))


def document_to_loaded_document(document: Mapping[str, Any]) -> LoadedDocument:
    """Normalize one JSON legal record for chunking and citation handling."""

    source = document.get("source") if isinstance(document.get("source"), Mapping) else {}
    document_info = document.get("document") if isinstance(document.get("document"), Mapping) else {}
    document_id = _text(document.get("id") or document.get("document_id") or source.get("filename")) or "document"
    title = _text(document.get("title") or document_info.get("title")) or document_id
    blocks: list[DocumentBlock] = []
    primary_text = _primary_document_text(document)
    if primary_text:
        blocks.append(DocumentBlock(text=primary_text))
    else:
        for article in document.get("articles", []) or []:
            article_text = _without_summary_sections(article.get("text"))
            if article_text:
                blocks.append(
                    DocumentBlock(
                        text=article_text,
                        page_number=int(article.get("page_number") or 1),
                        article_reference=_text(article.get("article_number")),
                    )
                )
    metadata = {
        key: value
        for key, value in {
            "document_id": document_id,
            "document_type": _text(document.get("document_type") or document_info.get("type")),
            "law_number": _text(document.get("law_number") or document_info.get("decision_number")),
            "year": _text(document.get("year") or document_info.get("year")),
            "source": _text(source.get("filename") or document.get("source")),
            "category": document.get("category"),
            "upload_id": _text(document.get("upload_id")),
            "original_filename": _text(document.get("original_filename")),
            "original_json_path": _text(
                document.get("original_json_path")
                or document.get("source_json_path")
                or document.get("json_path")
                or document.get("path")
            ),
            "has_full_source_text": bool(primary_text),
        }.items()
        if value not in (None, "", [], {})
    }
    return LoadedDocument(
        source_file=_text(source.get("filename") or document.get("source")) or document_id,
        source_type="json",
        title=title,
        blocks=blocks,
        document_type=_text(document.get("document_type") or document_info.get("type")),
        metadata=metadata,
    )


def documents_to_loaded_documents(documents: Iterable[Mapping[str, Any]]) -> list[LoadedDocument]:
    return [document_to_loaded_document(document) for document in documents]


def load_json_documents() -> list[LoadedDocument]:
    repository = JsonRepository()
    return documents_to_loaded_documents(repository.list_documents())
