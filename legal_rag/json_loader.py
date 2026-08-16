"""Load independent parser JSON output for the Legal RAG pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from app.config import PROJECT_ROOT
    from app.arabic_search import normalized_search_blob
    from app.legal_source_text import source_text_from_payload
    from app.text_encoding import repair_json_text
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    def source_text_from_payload(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        long_text = str(payload.get("long_text") or "")
        if long_text.strip():
            return long_text
        body = str(payload.get("body") or "")
        if body.strip():
            return body
        paragraphs = payload.get("paragraphs") or []
        return "\n".join(
            str(item.get("text") if isinstance(item, dict) else item).strip()
            for item in paragraphs
            if str(item.get("text") if isinstance(item, dict) else item).strip()
        )

    def normalized_search_blob(value: Any) -> str:
        return str(value or "")

    def repair_json_text(value: Any) -> Any:
        return value


LEGAL_JSON_OUTPUT_DIR = PROJECT_ROOT / "legal_document_parser" / "output" / "json"


@dataclass(frozen=True)
class DocumentSearchRecord:
    """Unified internal representation used for legal document search."""

    document_id: str
    filename: str
    title: str
    document_type: str
    decision_number: str | None
    year: str
    issue_date: str
    session_number: str
    session_date: str
    references: list[dict[str, Any]]
    entities: list[str]
    search_text: str
    long_text: str


@dataclass(frozen=True)
class LoadedLegalJson:
    """Structured legal JSON prepared for legal chunking."""

    document_id: str
    source_path: Path
    source_file: str
    long_text: str
    document: dict[str, Any]
    metadata: dict[str, Any]
    sections: list[dict[str, Any]]
    legal_items: list[dict[str, Any]]
    paragraphs: list[dict[str, Any]]
    references: list[dict[str, Any]]
    entities: dict[str, Any]
    search_record: DocumentSearchRecord
    raw: dict[str, Any]


def _stable_document_id(payload: dict[str, Any], source_path: Path) -> str:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    filename = str(source.get("filename") or source_path.name)
    year = str((payload.get("document") or {}).get("year") or "")
    title = str((payload.get("document") or {}).get("title") or filename)
    digest = hashlib.sha1(f"{filename}|{year}|{title}".encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"legal_json_{digest}"


def primary_document_text(payload: dict[str, Any]) -> str:
    """Return the full legal text using the supported JSON precedence."""

    return source_text_from_payload(payload)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _flatten_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_flatten_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_flatten_values(item))
    else:
        text = _text(value)
        if text:
            values.append(text)
    return values


def _reference_texts(references: list[dict[str, Any]]) -> list[str]:
    values = []
    for reference in references:
        if isinstance(reference, dict):
            values.extend(_flatten_values(reference))
        else:
            values.append(_text(reference))
    return values


def build_search_record(
    payload: dict[str, Any],
    source_path: Path,
    *,
    document_id: str,
    long_text: str,
) -> DocumentSearchRecord:
    """Create the unified search record for one supported legal JSON payload."""

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    references = list(payload.get("references") or [])
    legal_entities = payload.get("legal_entities") if isinstance(payload.get("legal_entities"), dict) else {}
    extracted_fields = payload.get("extracted_fields") if isinstance(payload.get("extracted_fields"), dict) else {}

    filename = _text(source.get("filename") or metadata.get("source_filename") or source_path.name)
    title = _text(document.get("title") or metadata.get("title") or filename)
    document_type = _text(document.get("type") or metadata.get("document_type"))
    decision_number = _text(document.get("decision_number") or metadata.get("decision_number")) or None
    year = _text(document.get("year") or metadata.get("year"))
    issue_date = _text(document.get("issue_date") or metadata.get("issue_date"))
    session_number = _text(document.get("session_number") or metadata.get("session_number"))
    session_date = _text(document.get("session_date") or metadata.get("session_date"))
    entities = list(dict.fromkeys(_flatten_values(legal_entities)))

    search_values = [
        title,
        document_type,
        decision_number or "",
        year,
        issue_date,
        session_number,
        session_date,
    ]
    search_values.extend(_flatten_values(metadata))
    search_values.extend(_reference_texts(references))
    search_values.extend(entities)
    search_values.extend(_flatten_values(extracted_fields))
    search_values.append(long_text)
    raw_search_text = "\n".join(dict.fromkeys(value for value in search_values if value)).strip()
    normalized_search_text = normalized_search_blob(raw_search_text)
    search_text = "\n".join(
        dict.fromkeys(value for value in (raw_search_text, normalized_search_text) if value)
    ).strip()

    return DocumentSearchRecord(
        document_id=document_id,
        filename=filename,
        title=title,
        document_type=document_type,
        decision_number=decision_number,
        year=year,
        issue_date=issue_date,
        session_number=session_number,
        session_date=session_date,
        references=references,
        entities=entities,
        search_text=search_text,
        long_text=long_text,
    )


def load_legal_json_file(source_path: Path) -> LoadedLegalJson:
    """Read one generated legal JSON file and expose RAG-relevant fields."""

    payload = repair_json_text(json.loads(source_path.read_text(encoding="utf-8-sig")))
    if not isinstance(payload, dict):
        raise ValueError(f"{source_path} does not contain a JSON object.")
    long_text = primary_document_text(payload)
    if not long_text.strip():
        raise ValueError(f"{source_path} is missing long_text and body fallback.")

    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    document = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    entities = payload.get("legal_entities") if isinstance(payload.get("legal_entities"), dict) else {}

    document_id = _stable_document_id(payload, source_path)
    search_record = build_search_record(
        payload,
        source_path,
        document_id=document_id,
        long_text=long_text,
    )

    return LoadedLegalJson(
        document_id=document_id,
        source_path=source_path,
        source_file=search_record.filename,
        long_text=long_text,
        document=document,
        metadata=metadata,
        sections=list(decision.get("sections") or []),
        legal_items=list(decision.get("numbered_items") or []),
        paragraphs=list(payload.get("paragraphs") or []),
        references=list(payload.get("references") or []),
        entities=entities,
        search_record=search_record,
        raw=payload,
    )


def load_legal_json_documents(input_dir: Path = LEGAL_JSON_OUTPUT_DIR) -> list[LoadedLegalJson]:
    """Load every JSON document produced by the independent parser."""

    if not input_dir.exists():
        return []
    return [load_legal_json_file(path) for path in sorted(input_dir.glob("*.json"))]
