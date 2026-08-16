"""End-to-end Iraqi government document preprocessing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.iraqi_government.builder import build_standard_json
from app.iraqi_government.extractor import extract_fixed_metadata, extract_legal_content
from app.iraqi_government.loader import load_document
from app.iraqi_government.storage import save_standard_json
from app.iraqi_government.validator import validate_standard_json


def process_document(
    source_path: str | Path,
    output_path: str | Path | None = None,
    *,
    require_valid: bool = True,
) -> dict[str, Any]:
    """Run all Phase 1 preprocessing steps for one source document.

    This function is deliberately independent from the RAG pipeline: it performs
    no embedding, indexing, chunking, retrieval, or model calls.
    """

    loaded = load_document(source_path)
    metadata = extract_fixed_metadata(loaded.text, loaded.filename)
    content = extract_legal_content(loaded.text)
    payload = build_standard_json(loaded, metadata, content)
    validation = validate_standard_json(payload)
    payload["validation"] = {
        "valid": validation.valid,
        "errors": validation.errors,
    }

    if require_valid and not validation.valid:
        raise ValueError("Invalid Iraqi government document JSON: " + "; ".join(validation.errors))

    if output_path is not None:
        save_standard_json(payload, output_path)

    return payload
