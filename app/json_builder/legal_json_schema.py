"""Unified JSON schema for processed legal documents."""

from __future__ import annotations

from typing import Any


def build_unified_legal_json(document: dict[str, Any]) -> dict[str, Any]:
    """Build a standardized JSON payload from the extracted document fields."""

    metadata = dict(document.get("metadata") or {})
    semantic_fields = dict(document.get("semantic_fields") or {})
    legal_structure = dict(document.get("legal_structure") or {})

    return {
        "document_classification": {
            "category": document.get("document_type") or document.get("category") or "",
            "confidence": document.get("document_type_confidence", 0.0),
            "reason": document.get("document_type_reason", ""),
        },
        "extracted_metadata": metadata,
        "legal_structure": legal_structure,
        "legal_entities": {
            "responsible_entities": semantic_fields.get("responsible_entities", []),
            "affected_organizations": semantic_fields.get("affected_organizations", []),
        },
        "legal_references": {
            "references": semantic_fields.get("legal_references", []),
            "mentioned_laws": metadata.get("mentioned_laws", []),
            "mentioned_decisions": metadata.get("mentioned_decisions", []),
        },
        "financial_values": [],
        "dates": [metadata.get("issue_date", "")],
        "organizations": [
            *[metadata.get("ministry", "")],
            *[metadata.get("department", "")],
            *semantic_fields.get("affected_organizations", []),
        ],
        "implementation_actions": semantic_fields.get("implementation_requirements", []),
        "original_text": document.get("original_text", ""),
        "cleaned_text": document.get("cleaned_text", ""),
    }
