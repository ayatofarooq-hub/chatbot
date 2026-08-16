"""Rule-based legal structure extraction for known document categories."""

from __future__ import annotations

import re
from typing import Any


def extract_legal_structure(document_type: str, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract the legal structure for cabinet decisions or ministry letters."""

    metadata = metadata or {}
    normalized = text or ""
    structure: dict[str, Any] = {"document_type": document_type, "sections": []}

    if document_type.lower() == "cabinet decision":
        structure["sections"] = [
            {
                "name": "introductory_legal_basis",
                "content": _extract_section(normalized, [r"legal basis", r"based on", r"pursuant to"]),
            },
            {
                "name": "decision_paragraphs",
                "content": _extract_paragraphs(normalized, [r"decision", r"resolved", r"hereby"]),
            },
            {
                "name": "numbered_items",
                "content": _extract_list_items(normalized, r"^\d+\.\s+"),
            },
            {
                "name": "sub_items",
                "content": _extract_list_items(normalized, r"^\s*[-*]\s+"),
            },
            {
                "name": "legal_references",
                "content": _extract_section(normalized, [r"article", r"law", r"regulation", r"decision"]),
            },
            {
                "name": "responsibilities",
                "content": _extract_section(normalized, [r"responsible", r"shall", r"must"]),
            },
            {
                "name": "implementation_clauses",
                "content": _extract_section(normalized, [r"implementation", r"implemented", r"effective"]),
            },
            {
                "name": "exceptions",
                "content": _extract_section(normalized, [r"except", r"excluding", r"unless"]),
            },
        ]
    elif document_type.lower() == "ministry letter":
        structure["sections"] = [
            {
                "name": "subject",
                "content": _extract_section(normalized, [r"subject", r"title"]),
            },
            {
                "name": "forwarding_purpose",
                "content": _extract_section(normalized, [r"forward", r"purpose", r"for the purpose"]),
            },
            {
                "name": "referenced_cabinet_decision",
                "content": metadata.get("decision_number") or _extract_section(normalized, [r"cabinet decision", r"decision no"]),
            },
            {
                "name": "attachments",
                "content": _extract_section(normalized, [r"attachment", r"annex"]),
            },
            {
                "name": "requested_action",
                "content": _extract_section(normalized, [r"request", r"requested", r"kindly"]),
            },
            {
                "name": "recipients",
                "content": _extract_section(normalized, [r"to", r"recipient"]),
            },
        ]

    return structure


def _extract_section(text: str, patterns: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches: list[str] = []
    for line in lines:
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns):
            matches.append(line)
    return "\n".join(matches[:8])


def _extract_paragraphs(text: str, patterns: list[str]) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    matches: list[str] = []
    for paragraph in paragraphs:
        if any(re.search(pattern, paragraph, flags=re.IGNORECASE) for pattern in patterns):
            matches.append(paragraph)
    return "\n".join(matches[:8])


def _extract_list_items(text: str, pattern: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches = [line for line in lines if re.match(pattern, line)]
    return "\n".join(matches[:10])
