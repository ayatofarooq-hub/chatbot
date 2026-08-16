"""Semantic extraction with Qwen 2.5 1.5B for non-rule-based fields only."""

from __future__ import annotations

import json
from typing import Any

from app.config import DOCUMENT_INFO_MODEL, OLLAMA_KEEP_ALIVE


def build_semantic_extraction_prompt(cleaned_text: str, metadata: dict[str, Any]) -> str:
    """Build a strict prompt for semantic extraction from the cleaned document."""

    metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            "You are a legal document extractor.",
            "Use the cleaned document text and the already extracted metadata below.",
            "Extract only information that cannot be reliably obtained by rules.",
            "Do not generate explanations, opinions, or free-form prose.",
            "Return valid JSON only.",
            "",
            "Required JSON schema:",
            '{"executive_summary": "...", "legal_objective": "...", "decision_outcome": "...", "obligations": [], "responsible_entities": [], "implementation_requirements": [], "legal_references": [], "affected_organizations": [], "legal_keywords": []}',
            "",
            "Metadata:",
            metadata_json,
            "",
            "Cleaned document text:",
            cleaned_text,
        ]
    )


def parse_semantic_extraction_response(content: str) -> dict[str, Any]:
    """Parse the model response into a JSON object."""

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        return {
            "executive_summary": "",
            "legal_objective": "",
            "decision_outcome": "",
            "obligations": [],
            "responsible_entities": [],
            "implementation_requirements": [],
            "legal_references": [],
            "affected_organizations": [],
            "legal_keywords": [],
        }

    return {
        "executive_summary": str(payload.get("executive_summary", "")).strip(),
        "legal_objective": str(payload.get("legal_objective", "")).strip(),
        "decision_outcome": str(payload.get("decision_outcome", "")).strip(),
        "obligations": [str(item).strip() for item in payload.get("obligations", []) if str(item).strip()],
        "responsible_entities": [str(item).strip() for item in payload.get("responsible_entities", []) if str(item).strip()],
        "implementation_requirements": [str(item).strip() for item in payload.get("implementation_requirements", []) if str(item).strip()],
        "legal_references": [str(item).strip() for item in payload.get("legal_references", []) if str(item).strip()],
        "affected_organizations": [str(item).strip() for item in payload.get("affected_organizations", []) if str(item).strip()],
        "legal_keywords": [str(item).strip() for item in payload.get("legal_keywords", []) if str(item).strip()],
    }


def extract_semantic_fields(cleaned_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Ask Qwen 2.5 1.5B for semantic extraction only."""

    from app.ollama_client import client

    response = client.chat(
        model=DOCUMENT_INFO_MODEL,
        messages=[{"role": "user", "content": build_semantic_extraction_prompt(cleaned_text, metadata)}],
        stream=False,
        keep_alive=OLLAMA_KEEP_ALIVE,
        options={"temperature": 0, "num_predict": 600},
    )

    return parse_semantic_extraction_response(response["message"]["content"].strip())
