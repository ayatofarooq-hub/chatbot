"""Qwen legal analysis component for parser-only structured extraction."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from config import OLLAMA_MODEL
from models.document import (
    CleanedDocument,
    DocumentMetadata,
    DocumentTypeDetection,
    LlmLegalAnalysis,
)
from prompts.legal_analysis import LEGAL_ANALYSIS_PROMPT
from utils.json_utils import parse_json_object
from utils.ollama_client import LocalOllamaClient


class QwenLegalAnalyzer:
    """Use Qwen through local Ollama to produce JSON-only legal analysis."""

    def __init__(self, client: LocalOllamaClient | None = None) -> None:
        self.client = client or LocalOllamaClient()

    def analyze(
        self,
        document: CleanedDocument,
        metadata: DocumentMetadata,
        document_type: DocumentTypeDetection,
        include_summary: bool = True,
        requested_fields: list[str] | None = None,
    ) -> LlmLegalAnalysis:
        fields = requested_fields or [
            "legal_meaning",
            "legal_entities",
            "structured_fields",
            "summary",
        ]
        prompt = LEGAL_ANALYSIS_PROMPT.format(
            document_type=document_type.document_type,
            metadata_json=json.dumps(asdict(metadata), ensure_ascii=False),
            requested_fields_json=json.dumps(fields, ensure_ascii=False),
            document_text=self._truncate(document.raw_text),
        )
        parsed = parse_json_object(self.client.generate_json(prompt))
        if not include_summary:
            parsed["summary"] = None
        return self._to_analysis(parsed)

    def _to_analysis(self, parsed: dict[str, Any]) -> LlmLegalAnalysis:
        structured_fields = parsed.get("structured_fields")
        if not isinstance(structured_fields, dict):
            structured_fields = {}
        for field_name in (
            "legal_objective",
            "executive_summary",
            "implementation_responsibilities",
            "decision_outcome",
            "legal_references",
            "affected_entities",
        ):
            if field_name in parsed and field_name not in structured_fields:
                structured_fields[field_name] = parsed[field_name]

        return LlmLegalAnalysis(
            legal_meaning=self._optional_string(parsed.get("legal_meaning")),
            legal_entities=self._entity_list(parsed.get("legal_entities")),
            structured_fields=structured_fields,
            summary=self._optional_string(parsed.get("summary")),
            model=OLLAMA_MODEL,
        )

    def _entity_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _optional_string(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    def _truncate(self, text: str, max_chars: int = 12000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars]
