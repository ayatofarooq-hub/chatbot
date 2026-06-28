"""Map PostgreSQL Iraqi-law rows into the legal document pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

try:
    from .database import (
        create_database_engine,
        database_url,
        iter_iraqi_laws,
    )
    from .legal_document import DocumentBlock, LoadedDocument
except ImportError:
    from database import create_database_engine, database_url, iter_iraqi_laws
    from legal_document import DocumentBlock, LoadedDocument


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def law_reference(row: Mapping[str, Any]) -> str:
    """Build a readable law reference from one database row."""

    reference = _text(row.get("law_name"))
    law_number = _text(row.get("law_number"))
    law_year = _text(row.get("law_year"))
    if law_number:
        reference += f" رقم {law_number}"
    if law_year:
        reference += f" لسنة {law_year}"
    return reference.strip()


def row_to_document(row: Mapping[str, Any]) -> LoadedDocument:
    """Convert one public.iraqi_laws row to a structured source document."""

    row_id = _text(row.get("id"))
    if not row_id:
        raise ValueError("An iraqi_laws row is missing its id.")

    title = _text(row.get("law_name"))
    if not title:
        raise ValueError(f"iraqi_laws row {row_id} is missing law_name.")

    article_number = _text(row.get("article_number"))
    article_reference = f"المادة {article_number}" if article_number else ""
    summary = _text(row.get("summary"))
    content_lines = [
        law_reference(row),
        article_reference,
        summary,
    ]
    content = "\n".join(value for value in content_lines if value)

    return LoadedDocument(
        source_file=f"postgres_iraqi_laws_{row_id}",
        source_type="postgresql",
        title=title,
        blocks=[
            DocumentBlock(
                text=content,
                article_reference=article_reference,
            )
        ],
        document_type=_text(row.get("classification")),
        metadata={
            key: value
            for key, value in {
                "database_table": "public.iraqi_laws",
                "database_id": row_id,
                "classification": _text(row.get("classification")),
                "law_number": _text(row.get("law_number")),
                "law_year": _text(row.get("law_year")),
                "article_number": article_number,
                "law_name": title,
                "law_reference": law_reference(row),
            }.items()
            if value
        },
    )


def rows_to_documents(
    rows: Iterable[Mapping[str, Any]],
) -> list[LoadedDocument]:
    """Convert database rows to structured legal documents."""

    return [row_to_document(row) for row in rows]


def load_postgres_documents() -> list[LoadedDocument]:
    """Load all configured PostgreSQL Iraqi-law records."""

    if not database_url(required=False):
        return []

    engine = create_database_engine()
    try:
        return rows_to_documents(iter_iraqi_laws(engine))
    finally:
        engine.dispose()
