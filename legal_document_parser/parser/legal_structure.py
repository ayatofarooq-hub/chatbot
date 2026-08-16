"""Extract legal sections, numbered items, paragraphs, and signature block."""

from __future__ import annotations

import re
from typing import Any


ITEM_RE = re.compile(r"^(أولًا|أولا|ثانيًا|ثانيا|ثالثًا|ثالثا|رابعًا|رابعا|خامسًا|خامسا)\s*[:：]?\s*(.*)")
ARTICLE_RE = re.compile(r"^المادة\s*\(([^)]{1,80})\)\s*(.*)")
SIGNATURE_WORD_RE = re.compile(r"(?:الأمين|الامين|الوزير|المدير|الرئيس)")


class LegalStructureExtractor:
    """Build a simple, source-preserving legal structure."""

    def extract(self, paragraphs: list[str]) -> dict[str, Any]:
        paragraph_items = [
            {"index": index, "text": paragraph}
            for index, paragraph in enumerate(paragraphs, start=1)
        ]
        numbered_items = self._numbered_items(paragraphs)
        sections = self._sections(paragraphs, numbered_items)
        return {
            "sections": sections,
            "numbered_items": numbered_items,
            "paragraphs": paragraph_items,
            "signature": self._signature_block(paragraphs),
        }

    def _sections(self, paragraphs: list[str], numbered_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        if paragraphs:
            sections.append(
                {
                    "section_id": "header",
                    "title": "header",
                    "paragraph_indexes": [1, 2, 3][: len(paragraphs)],
                    "text": "\n".join(paragraphs[:3]),
                }
            )
        if numbered_items:
            paragraph_indexes = [item["paragraph_index"] for item in numbered_items]
            start = min(paragraph_indexes)
            end = max(paragraph_indexes)
            section_paragraphs = paragraphs[start - 1 : end]
            sections.append(
                {
                    "section_id": "decision_body",
                    "title": "decision_body",
                    "paragraph_indexes": list(range(start, end + 1)),
                    "text": "\n".join(section_paragraphs),
                }
            )
        signature = self._signature_block(paragraphs)
        if signature:
            sections.append(
                {
                    "section_id": "signature",
                    "title": "signature",
                    "paragraph_indexes": signature["paragraph_indexes"],
                    "text": signature["text"],
                }
            )
        return sections

    def _numbered_items(self, paragraphs: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            item_match = ITEM_RE.match(paragraph)
            article_match = ARTICLE_RE.match(paragraph)
            if item_match:
                items.append(
                    {
                        "kind": "ordinal_item",
                        "number": item_match.group(1),
                        "paragraph_index": index,
                        "text": paragraph,
                    }
                )
            elif article_match:
                items.append(
                    {
                        "kind": "article_reference",
                        "number": article_match.group(1).strip(),
                        "paragraph_index": index,
                        "text": paragraph,
                    }
                )
        return items

    def _signature_block(self, paragraphs: list[str]) -> dict[str, Any] | None:
        for index, paragraph in enumerate(paragraphs):
            normalized = self._normalize(paragraph)
            if len(paragraph) <= 90 and SIGNATURE_WORD_RE.search(normalized):
                start = max(0, index - 1)
                end = min(len(paragraphs), index + 2)
                block = paragraphs[start:end]
                return {
                    "paragraph_indexes": list(range(start + 1, end + 1)),
                    "text": "\n".join(block),
                }
        return None

    def _normalize(self, value: str) -> str:
        value = re.sub(r"[\u064b-\u065f\u0670\u0640ـ]+", "", value)
        return value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
