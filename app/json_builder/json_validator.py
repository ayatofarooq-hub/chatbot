"""Validation helpers for unified legal JSON payloads."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def validate_legal_json(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a unified legal JSON payload and return (is_valid, errors)."""

    errors: list[str] = []

    if not isinstance(payload, dict):
        return False, ["payload must be a dictionary"]

    document_classification = payload.get("document_classification", {})
    if not isinstance(document_classification, dict):
        errors.append("document_classification must be an object")
    elif not document_classification.get("category"):
        errors.append("missing document classification category")

    metadata = payload.get("extracted_metadata", {})
    if not isinstance(metadata, dict):
        errors.append("extracted_metadata must be an object")

    legal_structure = payload.get("legal_structure", {})
    if not isinstance(legal_structure, dict):
        errors.append("legal_structure must be an object")
    else:
        sections = legal_structure.get("sections") or []
        if not isinstance(sections, list) or not sections:
            errors.append("legal_structure sections are missing")
        else:
            names = [section.get("name") for section in sections if isinstance(section, dict)]
            if len(names) != len(set(names)):
                errors.append("duplicate sections detected")

    title = payload.get("document_title") or payload.get("title")
    if not title:
        title = payload.get("document_classification", {}).get("category")
    if not title:
        errors.append("missing title")

    for date_value in payload.get("dates", []) or []:
        if isinstance(date_value, str) and date_value.strip():
            try:
                datetime.fromisoformat(date_value.replace("/", "-"))
            except ValueError:
                errors.append(f"invalid date: {date_value}")

    if not payload.get("cleaned_text", "").strip():
        errors.append("cleaned text is empty")

    if not payload.get("original_text", "").strip():
        errors.append("original text is empty")

    numbering_sequences = _extract_numbering_sequences(payload)
    for sequence in numbering_sequences:
        if not sequence:
            continue
        if sequence != sorted(sequence):
            errors.append("legal numbering sequence is invalid")
            break

    return not errors, errors


def _extract_numbering_sequences(payload: dict[str, Any]) -> list[list[int]]:
    sequences: list[list[int]] = []
    for section in payload.get("legal_structure", {}).get("sections", []) or []:
        content = section.get("content", "") if isinstance(section, dict) else ""
        numbers = [int(match) for match in __import__("re").findall(r"\b(\d+)\b", str(content))]
        if numbers:
            sequences.append(numbers)
    return sequences


def validate_json_syntax(text: str) -> tuple[bool, list[str]]:
    """Validate that the text is valid JSON syntax."""

    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return False, [f"invalid json syntax: {exc}"]
    return True, []
