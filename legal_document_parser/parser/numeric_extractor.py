"""Extract numeric values while preserving their source wording."""

from __future__ import annotations

import re
from typing import Any


AMOUNT_RE = re.compile(r"\([\d.,\u0660-\u0669]+\)\s*(?:دولار|دينار|%|كم|ملم|يوم|طائرة|عقدة)?")
NUMBER_RE = re.compile(r"\([\d.,/\-\u0660-\u0669]+\)")


class NumericExtractor:
    """Collect monetary and other numeric mentions."""

    def extract(self, text: str) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for match in AMOUNT_RE.finditer(text):
            raw = self._clean(match.group(0))
            values.append({"type": self._type(raw), "text": raw})
        for match in NUMBER_RE.finditer(text):
            raw = self._clean(match.group(0))
            values.append({"type": "number", "text": raw})
        return self._dedupe(values)

    def _type(self, value: str) -> str:
        if "دولار" in value or "دينار" in value:
            return "money"
        if "%" in value:
            return "percentage"
        return "quantity"

    def _dedupe(self, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        unique = []
        for value in values:
            key = value["text"]
            if key in seen:
                continue
            seen.add(key)
            unique.append(value)
        return unique

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

