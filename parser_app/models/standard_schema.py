"""Standard Iraqi legal document JSON schema helpers."""

from __future__ import annotations

from typing import Any


STANDARD_SCHEMA_VERSION = "iraqi_legal_document.v2"

STANDARD_TOP_LEVEL_KEYS = (
    "schema_version",
    "source",
    "document",
    "metadata",
    "references",
    "decision",
    "body",
    "paragraphs",
    "legal_entities",
    "extracted_fields",
    "signature",
)

BANNED_SCHEMA_KEYS = {
    "chroma",
    "chromadb",
    "embedding",
    "embeddings",
    "vector",
    "vectors",
    "retrieval",
    "retriever",
    "chunk_id",
    "chunk_ids",
    "collection",
    "collection_name",
    "distance",
    "score",
}


def find_banned_keys(value: Any) -> list[str]:
    found: list[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized = str(key).lower()
                if normalized in BANNED_SCHEMA_KEYS:
                    found.append(str(key))
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found
