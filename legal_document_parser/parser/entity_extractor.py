"""Rule-based legal entity extraction."""

from __future__ import annotations

import re
from typing import Any


ORG_RE = re.compile(
    r"(?:وزارة|مجلس|شركة|المجلس|الأمانة|الامانة|الدائرة|مكتب|ديوان|محافظة|هيئة|الهيئة|مكتب التعاون الأمني)"
    r"[\u0600-\u06ffA-Za-z0-9\s()/\-]{1,70}?"
    r"(?=\s+(?:بموجب|والتي|وتتحمل|صحة|سلامة|من|في|على)|[،.:\n]|$)"
)
COMPANY_RE = re.compile(r"شركة\s*\([^)]{1,80}\)|شركة\s+[\u0600-\u06ffA-Za-z0-9\s]{2,80}")
PERSON_RE = re.compile(r"(?:د\.\s*)?[\u0600-\u06ff]{2,20}\s+[\u0600-\u06ff]{2,20}\s+[\u0600-\u06ff]{2,20}")


class EntityExtractor:
    """Extract named legal/government entities without model calls."""

    def extract(self, text: str) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        for match in ORG_RE.finditer(text):
            value = self._clean(match.group(0))
            if value:
                entities.append({"type": "organization", "name": value})
        for match in COMPANY_RE.finditer(text):
            value = self._clean(match.group(0))
            if value:
                entities.append({"type": "company", "name": value})
        for match in PERSON_RE.finditer(text):
            value = self._clean(match.group(0))
            if value and ("حميد" in value or value.startswith("د.")):
                entities.append({"type": "person", "name": value})
        return self._dedupe(entities)

    def _dedupe(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        unique = []
        for entity in entities:
            key = (entity["type"], entity["name"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(entity)
        return unique

    def _clean(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value).strip(" ،.:-")
        if len(cleaned) < 5 or cleaned in {"وزارة", "مجلس", "شركة"}:
            return None
        return cleaned
