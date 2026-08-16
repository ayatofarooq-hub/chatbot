"""Select complete legal source text from JSON payloads."""

from __future__ import annotations

from typing import Any


NO_USABLE_LEGAL_SOURCE_TEXT = "No usable legal source text found."


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_text_from_mapping(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    """Return the first non-empty string from a mapping."""

    for key in keys:
        text = _text(payload.get(key))
        if text:
            return text
    return ""


def reconstruct_from_paragraphs(paragraphs: Any) -> str:
    """Rebuild source text from paragraphs only when no full text exists."""

    if not isinstance(paragraphs, list):
        return ""
    parts = []
    for paragraph in paragraphs:
        if isinstance(paragraph, dict):
            text = _text(paragraph.get("text") or paragraph.get("body") or paragraph.get("content"))
        else:
            text = _text(paragraph)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def source_text_from_payload(payload: Any) -> str:
    """Return the best complete source text from supported legal JSON shapes."""

    if not isinstance(payload, dict):
        return ""

    direct_text = _first_text_from_mapping(
        payload,
        (
            "long_text",
            "body",
            "full_text",
            "original_long_text",
            "original_text",
            "content",
            "text",
        ),
    )
    if direct_text:
        return direct_text

    for nested_key in ("document", "raw_payload"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            nested_text = source_text_from_payload(nested)
            if nested_text:
                return nested_text

    return reconstruct_from_paragraphs(payload.get("paragraphs"))
