"""Validation helpers for generated JSON payloads."""

from typing import Any


REQUIRED_DOCUMENT_FIELDS = ("title", "summary", "document_type")


def validate_document_json(payload: dict[str, Any]) -> list[str]:
    """Print a warning when required final JSON fields are missing or empty."""

    missing_fields = [
        field
        for field in REQUIRED_DOCUMENT_FIELDS
        if field not in payload or not str(payload[field]).strip()
    ]
    if missing_fields:
        print(f"Warning: missing required fields: {', '.join(missing_fields)}")

    return missing_fields
