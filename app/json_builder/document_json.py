"""Build and save extracted document JSON."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from app.extractors import DocumentInfo, RegexMetadata
from app.schemas import DocumentModel


def build_document_json(
    document: DocumentModel,
    regex_metadata: RegexMetadata,
    qwen_info: DocumentInfo,
) -> dict[str, Any]:
    """Build the final JSON payload for one document."""

    return {
        "source_file": document.source_file,
        "title": qwen_info.title or document.title,
        "document_type": qwen_info.document_type,
        "summary": qwen_info.summary,
        "keywords": qwen_info.keywords,
        "entities": qwen_info.entities,
        "mentioned_laws": qwen_info.mentioned_laws,
        "mentioned_decisions": qwen_info.mentioned_decisions,
        "constitution": qwen_info.constitution,
        "legal_references": qwen_info.legal_references,
        "paragraphs": [asdict(paragraph) for paragraph in document.paragraphs],
        "tables": document.tables,
        "sections": document.sections,
        "regex_metadata": asdict(regex_metadata),
    }


def save_document_json(payload: dict[str, Any], output_file: Path) -> None:
    """Save one JSON payload as UTF-8."""

    output_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
