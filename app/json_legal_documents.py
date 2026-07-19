"""Map JSON-backed legal documents into the legal document pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

try:
    from .legal_document import DocumentBlock, LoadedDocument
    from .text_encoding import repair_mojibake
    from backend.services.json_repository import JsonRepository
except ImportError:
    from legal_document import DocumentBlock, LoadedDocument
    from text_encoding import repair_mojibake
    from backend.services.json_repository import JsonRepository


def _text(value: Any) -> str:
    return "" if value is None else repair_mojibake(str(value)).strip()


def document_to_loaded_document(document: Mapping[str, Any]) -> LoadedDocument:
    """Normalize one JSON legal record for chunking and citation handling."""

    document_id = _text(document.get("id")) or "document"
    title = _text(document.get("title")) or document_id
    blocks: list[DocumentBlock] = []
    for article in document.get("articles", []) or []:
        article_text = _text(article.get("text"))
        if article_text:
            blocks.append(
                DocumentBlock(
                    text=article_text,
                    page_number=int(article.get("page_number") or 1),
                    article_reference=_text(article.get("article_number")),
                )
            )
    if not blocks:
        summary = _text(document.get("summary"))
        blocks.append(DocumentBlock(text=summary or title))

    metadata = {
        key: value
        for key, value in {
            "document_id": document_id,
            "document_type": _text(document.get("document_type")),
            "law_number": _text(document.get("law_number")),
            "year": _text(document.get("year")),
            "source": _text(document.get("source")),
            "category": document.get("category"),
            "upload_id": _text(document.get("upload_id")),
            "original_filename": _text(document.get("original_filename")),
        }.items()
        if value not in (None, "", [], {})
    }
    return LoadedDocument(
        source_file=_text(document.get("source")) or document_id,
        source_type="json",
        title=title,
        blocks=blocks,
        document_type=_text(document.get("document_type")),
        metadata=metadata,
    )


def documents_to_loaded_documents(documents: Iterable[Mapping[str, Any]]) -> list[LoadedDocument]:
    return [document_to_loaded_document(document) for document in documents]


def load_json_documents() -> list[LoadedDocument]:
    repository = JsonRepository()
    return documents_to_loaded_documents(repository.list_documents())
