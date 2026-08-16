"""Legal reference extraction."""

from __future__ import annotations

import re
from typing import Any

from .metadata_extractor import DATE_PATTERN, MetadataExtractor


ARTICLE_RE = re.compile(r"المادة\s*\([^)]{1,80}\)(?:\s*من\s*[^.\n]+)?")
DECISION_RE = re.compile(r"قرار\s+مجلس\s+الوزراء\s*(?:رقم)?\s*\([^)]*\)?\s*لسنة\s*[\d\u0660-\u0669]{4}")
DATED_REF_RE = re.compile(r"(?:المؤرخ(?:ة)?|المؤرخة)\s+(?:في\s+)?(" + DATE_PATTERN + r")")


class ReferenceExtractor:
    """Collect references that appear in the legal text."""

    def __init__(self) -> None:
        self._metadata = MetadataExtractor()

    def extract(self, text: str) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        references.extend(
            {"type": "legal_article", "text": self._clean(match.group(0))}
            for match in ARTICLE_RE.finditer(text)
        )
        references.extend(
            {"type": "cabinet_decision", "text": self._clean(match.group(0))}
            for match in DECISION_RE.finditer(text)
        )
        references.extend(self._metadata.extract_reference_records(text))
        references.extend(
            {"type": "date_reference", "text": self._clean(match.group(1))}
            for match in DATED_REF_RE.finditer(text)
        )
        return self._dedupe(references)

    def _dedupe(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        unique = []
        for reference in references:
            key = (str(reference.get("type")), str(reference.get("text")))
            if key in seen or not key[1]:
                continue
            seen.add(key)
            unique.append(reference)
        return unique

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" ،.:-")
