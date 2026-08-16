"""Validation engine for generated Iraqi legal JSON files."""

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
from typing import Any

from config import DEFAULT_ENCODING
from models.standard_schema import (
    STANDARD_SCHEMA_VERSION,
    STANDARD_TOP_LEVEL_KEYS,
    find_banned_keys,
)


_DATE_FIELDS = (
    ("document", "issue_date"),
    ("document", "session", "date"),
    ("metadata", "issue_date"),
    ("metadata", "session_date"),
)
_DATE_FORMATS = ("%d/%m/%Y",)
_DATE_PATTERN = re.compile(r"^[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}$")
class ValidationError(ValueError):
    """Raised when generated JSON fails validation."""


class ValidationEngine:
    """Validate every generated legal document JSON object and file."""

    def validate_dict(self, document: dict[str, Any]) -> dict[str, Any]:
        self._validate_required_schema(document)
        self._validate_banned_fields(document)
        self._validate_required_fields(document)
        self._validate_missing_metadata(document)
        self._validate_invalid_dates(document)
        self._validate_sections(document)
        self._validate_paragraph_coverage(document)
        self._validate_legal_entities(document)
        self._validate_references(document)
        self._validate_extracted_fields(document)
        self._validate_signature(document)
        return document

    def validate_file(self, path: Path) -> dict[str, Any]:
        try:
            content = path.read_text(encoding=DEFAULT_ENCODING)
        except UnicodeDecodeError as exc:
            raise ValidationError(f"File is not valid UTF-8: {path}") from exc

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"File does not contain valid JSON: {path}") from exc

        if not isinstance(parsed, dict):
            raise ValidationError("Generated JSON root must be an object")

        return self.validate_dict(parsed)

    def _validate_required_schema(self, document: dict[str, Any]) -> None:
        if tuple(document.keys()) != STANDARD_TOP_LEVEL_KEYS:
            raise ValidationError("JSON does not follow the standard top-level schema")
        if document.get("schema_version") != STANDARD_SCHEMA_VERSION:
            raise ValidationError(f"schema_version must be {STANDARD_SCHEMA_VERSION}")

    def _validate_banned_fields(self, document: dict[str, Any]) -> None:
        banned_keys = find_banned_keys(document)
        if banned_keys:
            raise ValidationError(f"JSON contains banned retrieval/vector fields: {banned_keys}")

    def _validate_required_fields(self, document: dict[str, Any]) -> None:
        required_paths = (
            ("source", "filename"),
            ("source", "extension"),
            ("document", "type"),
            ("document", "title"),
            ("metadata",),
            ("references",),
            ("decision", "sections"),
            ("body",),
            ("paragraphs",),
            ("legal_entities",),
            ("extracted_fields",),
            ("signature",),
        )
        for path in required_paths:
            value = self._get_path(document, path)
            if value is None or value == "":
                raise ValidationError(f"Required field is missing: {'.'.join(path)}")

        if not isinstance(document.get("paragraphs"), list) or not document["paragraphs"]:
            raise ValidationError("paragraphs must be a non-empty list")

    def _validate_missing_metadata(self, document: dict[str, Any]) -> None:
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            raise ValidationError("metadata must be an object")

        missing_core = [
            key
            for key in ("issue_date", "subject", "sender", "signature")
            if metadata.get(key) in (None, "", [])
        ]
        if len(missing_core) >= 4:
            raise ValidationError(f"metadata is too sparse; missing: {missing_core}")

    def _validate_invalid_dates(self, document: dict[str, Any]) -> None:
        for path in _DATE_FIELDS:
            value = self._get_path(document, path)
            if value in (None, ""):
                continue
            if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value.strip()):
                raise ValidationError(f"Invalid date format: {'.'.join(path)}")
            self._parse_date(value)

    def _validate_sections(self, document: dict[str, Any]) -> None:
        section_items = self._get_path(document, ("decision", "sections"))
        if not isinstance(section_items, list):
            raise ValidationError("decision.sections must be a list")
        for index, item in enumerate(section_items, start=1):
            if not isinstance(item, dict):
                raise ValidationError("section_items entries must be objects")
            if item.get("id") != index:
                raise ValidationError("section_items ids must be sequential")
            if not isinstance(item.get("text"), str) or not item["text"]:
                raise ValidationError("section_items text must be a non-empty string")
            for key in ("entities", "money", "dates", "references"):
                if not isinstance(item.get(key), list):
                    raise ValidationError(f"section_items {key} must be a list")

    def _validate_paragraph_coverage(self, document: dict[str, Any]) -> None:
        paragraphs = document.get("paragraphs")
        section_items = self._get_path(document, ("decision", "sections"))
        if not isinstance(paragraphs, list) or not isinstance(section_items, list):
            return

        section_paragraphs: list[str] = []
        for item in section_items:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            section_paragraphs.extend(item["text"].split("\n"))

        if section_paragraphs != paragraphs:
            raise ValidationError("decision.sections must contain every paragraph exactly once and in order")

    def _validate_legal_entities(self, document: dict[str, Any]) -> None:
        legal_entities = document.get("legal_entities")
        required_entity_keys = (
            "ministries",
            "companies",
            "committees",
            "authorities",
            "government_offices",
            "people",
            "projects",
            "councils",
        )
        if not isinstance(legal_entities, dict):
            raise ValidationError("legal_entities must be an object")
        for key in required_entity_keys:
            if not isinstance(legal_entities.get(key), list):
                raise ValidationError(f"legal_entities.{key} must be a list")

    def _validate_references(self, document: dict[str, Any]) -> None:
        references = document.get("references")
        if not isinstance(references, list):
            raise ValidationError("references must be a list")
        for item in references:
            if not isinstance(item, dict):
                raise ValidationError("references entries must be objects")
            if not isinstance(item.get("type"), str) or not item["type"]:
                raise ValidationError("references.type must be a non-empty string")
            if not isinstance(item.get("text"), str) or not item["text"]:
                raise ValidationError("references.text must be a non-empty string")

    def _validate_extracted_fields(self, document: dict[str, Any]) -> None:
        extracted_fields = document.get("extracted_fields")
        required_extracted_field_keys = (
            "money",
            "percentages",
            "years",
            "durations",
            "pipe_lengths",
            "diameters",
            "thickness",
            "quantities",
        )
        if not isinstance(extracted_fields, dict):
            raise ValidationError("extracted_fields must be an object")
        for key in required_extracted_field_keys:
            if not isinstance(extracted_fields.get(key), list):
                raise ValidationError(f"extracted_fields.{key} must be a list")

    def _validate_signature(self, document: dict[str, Any]) -> None:
        signature = document.get("signature")
        if not isinstance(signature, dict):
            raise ValidationError("signature must be an object")
        for key in ("text", "name", "title"):
            value = signature.get(key)
            if value is not None and not isinstance(value, str):
                raise ValidationError(f"signature.{key} must be a string or null")

    def _parse_date(self, value: str) -> datetime:
        normalized = self._arabic_digits_to_ascii(value).replace(" ", "")
        for date_format in _DATE_FORMATS:
            try:
                return datetime.strptime(normalized, date_format)
            except ValueError:
                continue
        raise ValidationError(f"Invalid date value: {value}")

    def _get_path(self, document: dict[str, Any], path: tuple[str, ...]) -> Any:
        current: Any = document
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _arabic_digits_to_ascii(self, value: str) -> str:
        return value.translate(
            str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669", "0123456789")
        )
