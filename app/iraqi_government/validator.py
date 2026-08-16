"""Validation for Iraqi government standardized JSON."""

from __future__ import annotations

from typing import Any

from app.iraqi_government.builder import SCHEMA_VERSION
from app.iraqi_government.models import ValidationResult


REQUIRED_TOP_LEVEL = ("schema_version", "id", "source", "metadata", "legal_content", "processing")
REQUIRED_METADATA = ("title", "document_type", "country", "language", "status")
REQUIRED_CONTENT = ("preamble", "articles", "clauses", "full_text")


def validate_standard_json(payload: dict[str, Any]) -> ValidationResult:
    """Validate the standardized JSON shape and required legal fields."""

    errors: list[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in payload:
            errors.append(f"Missing top-level field: {key}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("Unsupported or missing schema_version")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        for key in REQUIRED_METADATA:
            if not metadata.get(key):
                errors.append(f"Missing metadata field: {key}")
        if metadata.get("document_type") == "unknown":
            errors.append("document_type could not be detected")

    content = payload.get("legal_content")
    if not isinstance(content, dict):
        errors.append("legal_content must be an object")
    else:
        for key in REQUIRED_CONTENT:
            if key not in content:
                errors.append(f"Missing legal_content field: {key}")
        if not str(content.get("full_text", "")).strip():
            errors.append("legal_content.full_text is empty")
        if not isinstance(content.get("articles", []), list):
            errors.append("legal_content.articles must be a list")
        if not isinstance(content.get("clauses", []), list):
            errors.append("legal_content.clauses must be a list")

    processing = payload.get("processing")
    if isinstance(processing, dict) and processing.get("rag_independent") is not True:
        errors.append("processing.rag_independent must be true")

    return ValidationResult(valid=not errors, errors=errors)
