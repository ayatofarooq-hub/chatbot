"""Build standardized JSON for Iraqi government documents."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from app.iraqi_government.models import (
    GovernmentMetadata,
    LegalContent,
    LoadedGovernmentDocument,
)


SCHEMA_VERSION = "iraqi-government-legal-document/v1"


def build_standard_json(
    loaded: LoadedGovernmentDocument,
    metadata: GovernmentMetadata,
    content: LegalContent,
) -> dict[str, Any]:
    """Build the stable JSON payload produced by this preprocessing module."""

    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": _build_id(metadata, loaded),
        "source": {
            "file": loaded.source_file,
            "path": loaded.source_path,
            "extension": loaded.extension,
            "loader_metadata": loaded.loader_metadata,
        },
        "metadata": asdict(metadata),
        "legal_content": {
            "preamble": content.preamble,
            "articles": [asdict(article) for article in content.articles],
            "clauses": content.clauses,
            "full_text": content.full_text,
        },
        "processing": {
            "module": "app.iraqi_government",
            "rag_independent": True,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    return payload


def _build_id(metadata: GovernmentMetadata, loaded: LoadedGovernmentDocument) -> str:
    document_type = metadata.document_type or "unknown"
    number = metadata.document_number or "unknown"
    year = metadata.year or "unknown"
    if number != "unknown" or year != "unknown":
        return f"{document_type}-{number}-{year}"
    return f"{document_type}-{_slugify(loaded.source_file)}"


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part) or "document"
