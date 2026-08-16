"""Save unified legal JSON payloads to the requested legal_documents folder."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def build_output_path(payload: dict[str, Any], output_root: str | Path | None = None) -> Path:
    """Build a deterministic output path under data/legal_documents."""

    root = Path(output_root or "data/legal_documents")
    if root.name != "legal_documents":
        root = root / "legal_documents"
    root.mkdir(parents=True, exist_ok=True)

    metadata = payload.get("extracted_metadata", {}) or {}
    document_type = payload.get("document_classification", {}).get("category", "document")
    year = _extract_year(metadata, payload.get("dates", []))
    decision_number = metadata.get("decision_number") or metadata.get("document_number") or metadata.get("letter_number") or ""
    ministry = _slugify(metadata.get("ministry") or metadata.get("department") or "")
    if not ministry:
        ministry = "document"
    if not decision_number:
        decision_number = "unknown"

    stem = f"{year}_{_slugify(document_type)}_{decision_number}_{ministry}".strip("_")
    filename = f"{stem}.json"
    return root / filename


def save_legal_json(payload: dict[str, Any], output_root: str | Path | None = None) -> Path:
    """Persist a unified legal JSON payload as UTF-8 JSON."""

    output_path = build_output_path(payload, output_root)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _extract_year(metadata: dict[str, Any], dates: list[Any]) -> str:
    for value in [metadata.get("decision_year"), metadata.get("issue_date")]:
        if isinstance(value, str) and value:
            match = re.search(r"(\d{4})", value)
            if match:
                return match.group(1)
    for value in dates:
        if isinstance(value, str):
            match = re.search(r"(\d{4})", value)
            if match:
                return match.group(1)
    return "unknown"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "document"
