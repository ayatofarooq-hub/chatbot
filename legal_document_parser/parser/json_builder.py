"""Build and validate parser JSON output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .docx_parser import ParsedDocx
from .entity_extractor import EntityExtractor
from .legal_structure import LegalStructureExtractor
from .metadata_extractor import MetadataExtractor
from .numeric_extractor import NumericExtractor
from .reference_extractor import ReferenceExtractor


class LegalJsonBuilder:
    """Create standalone legal JSON from a parsed DOCX object."""

    def __init__(self) -> None:
        self.metadata_extractor = MetadataExtractor()
        self.structure_extractor = LegalStructureExtractor()
        self.reference_extractor = ReferenceExtractor()
        self.entity_extractor = EntityExtractor()
        self.numeric_extractor = NumericExtractor()

    def build(self, document: ParsedDocx) -> dict[str, Any]:
        metadata = self.metadata_extractor.extract(
            document.filename,
            document.paragraphs,
            document.full_text,
        )
        structure = self.structure_extractor.extract(document.paragraphs)
        references = self.reference_extractor.extract(document.full_text)
        legal_entities = self.entity_extractor.extract(document.full_text)
        numeric_values = self.numeric_extractor.extract(document.full_text)
        signature = metadata["signature"] or structure["signature"] or {}
        entity_groups = self._group_entities(legal_entities)
        reference_numbers = self._reference_texts(references, "reference_number")
        recommendation_numbers = self._reference_texts(references, "recommendation_number")
        document_numbers = self._reference_texts(references, "document_number")

        return {
            "schema_version": "iraqi_legal_document.v2",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "filename": document.filename,
                "extension": ".docx",
                "parser": "legal_document_parser",
                "encoding": "utf-8",
            },
            "document": {
                "title": metadata["title"],
                "type": metadata["document_type"],
                "decision_number": metadata["decision_number"],
                "year": metadata["year"],
                "issue_date": metadata["issue_date"],
                "session_number": metadata["session_number"],
                "session_date": metadata["session_date"],
            },
            "metadata": metadata,
            "references": references,
            "decision": {
                "sections": structure["sections"],
                "numbered_items": structure["numbered_items"],
            },
            "long_text": document.full_text,
            "body": document.full_text,
            "paragraphs": structure["paragraphs"],
            "legal_entities": entity_groups,
            "extracted_fields": {
                "document_type": metadata["document_type"],
                "decision_number": metadata["decision_number"],
                "year": metadata["year"],
                "issue_date": metadata["issue_date"],
                "session_number": metadata["session_number"],
                "session_date": metadata["session_date"],
                "subject": metadata["subject"],
                "sender": metadata["sender"],
                "recipient": metadata["recipient"],
                "recommendation_numbers": recommendation_numbers,
                "reference_numbers": reference_numbers,
                "document_numbers": document_numbers,
                "numeric_values": numeric_values,
                "tables": document.tables,
            },
            "signature": signature,
            "extraction_notes": {
                "summarized": False,
                "truncated": False,
                "missing_information_policy": "null",
                "uses_chatbot": False,
                "uses_ollama": False,
                "uses_chromadb": False,
                "uses_postgresql": False,
            },
        }

    def _group_entities(self, entities: list[dict[str, Any]]) -> dict[str, Any]:
        grouped = {
            "organizations": [],
            "companies": [],
            "persons": [],
            "all": entities,
        }
        for entity in entities:
            if entity["type"] == "organization":
                grouped["organizations"].append(entity["name"])
            elif entity["type"] == "company":
                grouped["companies"].append(entity["name"])
            elif entity["type"] == "person":
                grouped["persons"].append(entity["name"])
        return grouped

    def _reference_texts(self, references: list[dict[str, Any]], reference_type: str) -> list[str]:
        values = [
            str(reference.get("text") or "").strip()
            for reference in references
            if reference.get("type") == reference_type and str(reference.get("text") or "").strip()
        ]
        return list(dict.fromkeys(values))


def validate_payload(payload: dict[str, Any], schema_path: Path) -> list[str]:
    """Validate against the local JSON schema and return errors."""

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        path = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{path}: {error.message}")
    long_text = str(payload.get("long_text") or "")
    body = str(payload.get("body") or "")
    paragraphs = payload.get("paragraphs")
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    sections = decision.get("sections") if isinstance(decision, dict) else None
    numbered_items = decision.get("numbered_items") if isinstance(decision, dict) else None

    if not long_text:
        errors.append("long_text must not be empty")
    if len(long_text) <= 0:
        errors.append("long_text length must be greater than 0")
    if not body and not long_text:
        errors.append("body fallback must not be empty when long_text is empty")
    if not isinstance(paragraphs, list) or not paragraphs:
        errors.append("paragraphs must exist and must not be empty")
    if not isinstance(sections, list) or not sections:
        errors.append("decision.sections must exist and must not be empty")
    if not isinstance(numbered_items, list):
        errors.append("decision.numbered_items must exist")

    for paragraph in paragraphs or []:
        text = str(paragraph.get("text") if isinstance(paragraph, dict) else "")
        if text and text not in long_text:
            errors.append(f"paragraph {paragraph.get('index')} is missing from long_text")
    for section in sections or []:
        text = str(section.get("text") if isinstance(section, dict) else "")
        if not text:
            errors.append(f"section {section.get('section_id')} has empty text")
        elif text not in long_text:
            errors.append(f"section {section.get('section_id')} is missing from long_text")
    for item in numbered_items or []:
        text = str(item.get("text") if isinstance(item, dict) else "")
        if not text:
            errors.append(f"numbered item {item.get('number')} has empty text")
        elif text not in long_text:
            errors.append(f"numbered item {item.get('number')} is missing from long_text")
    return errors
