"""Deterministic metadata extraction for Iraqi legal DOCX files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


DATE_PATTERN = r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}"
DATE_RE = re.compile(DATE_PATTERN)
DECISION_NUMBER_RE = re.compile(r"رق\s*ـ*\s*م\s*\(([^)]*)\)")
SESSION_RE = re.compile(
    r"جلس(?:ت|ـت)?\s*ه?\s+(?:الاعتيادية|العادية)?\s*(.{1,60}?)\s+المنعق(?:د|ـد)[ةه]?\s+(?:في\s+)?("
    + DATE_PATTERN
    + r")"
)
BOOK_RE = re.compile(
    r"(?:كتابها|كتابنا|المذكرة|مذكرتكم|رسالته|العدد)\s*(?:المرقم(?:ة)?\s+بالعدد)?\s*\(([^)]{2,120})\)"
)
SUBJECT_RE = re.compile(r"الموض\s*ـ*\s*وع\s*[/:\-]\s*(.+)")
YEAR_RE = re.compile(r"لسن\s*ـ*\s*ة\s*([\d\u0660-\u0669]{4})")
SIGNATURE_TITLE_RE = re.compile(r"(?:الأمي|الامي|الوزير|المدير|الرئيس).{0,50}")


BOOK_RE = re.compile(
    r"(?:\u0643\u062a\u0627\u0628\u0647\u0627|\u0643\u062a\u0627\u0628\u0646\u0627|\u0627\u0644\u0645\u0630\u0643\u0631\u0629|\u0645\u0630\u0643\u0631\u062a\u0643\u0645|\u0631\u0633\u0627\u0644\u062a\u0647|\u0627\u0644\u0639\u062f\u062f)\s*"
    r"(?:\u0627\u0644\u0645\u0631\u0642\u0645(?:\u0629)?\s+\u0628\u0627\u0644\u0639\u062f\u062f)?\s*\(([^)]{2,120})\)"
)
RECOMMENDATION_NUMBER_RE = re.compile(
    r"(?:\u062a\u0648\u0635\u064a\u0629|\u062a\u0648\u0635\u064a\u0627\u062a).{0,120}?\("
    r"((?=[^)]*[\d\u0660-\u0669])[^)]{1,80})\)"
)


class MetadataExtractor:
    """Extract core metadata without inventing missing values."""

    def extract(self, filename: str, paragraphs: list[str], full_text: str) -> dict[str, Any]:
        title = self._title(paragraphs, filename)
        signature = self._signature(paragraphs)
        issue_date = signature.get("date") if signature else None

        return {
            "source_filename": filename,
            "source_stem": Path(filename).stem,
            "title": title,
            "document_type": self._document_type(paragraphs, full_text),
            "decision_number": self._decision_number(paragraphs),
            "year": self._year(paragraphs, full_text, issue_date),
            "issue_date": issue_date or self._last_date(full_text),
            "session_number": self._session_number(full_text),
            "session_date": self._session_date(full_text),
            "subject": self._subject(full_text),
            "sender": self._sender(paragraphs),
            "recipient": self._recipient(paragraphs),
            "signature": signature,
            "source_character_count": len(full_text),
            "source_paragraph_count": len(paragraphs),
        }

    def _title(self, paragraphs: list[str], filename: str) -> str:
        if len(paragraphs) >= 2 and "قرار" in self._normalize(paragraphs[0]):
            return " ".join(paragraphs[:2])
        return next((paragraph for paragraph in paragraphs if paragraph.strip()), Path(filename).stem)

    def _document_type(self, paragraphs: list[str], text: str) -> str | None:
        normalized = self._normalize("\n".join(paragraphs[:5]) or text)
        if "قرار" in normalized and "مجلس الوزراء" in normalized:
            return "قرار مجلس الوزراء"
        if "الموضوع" in normalized and "قرار مجلس الوزراء" in self._normalize(text):
            return "كتاب إرفاق قرار مجلس الوزراء"
        if "قانون" in normalized:
            return "قانون"
        return None

    def _decision_number(self, paragraphs: list[str]) -> str | None:
        for paragraph in paragraphs[:8]:
            match = DECISION_NUMBER_RE.search(self._normalize(paragraph))
            if match:
                cleaned = self._clean(match.group(1))
                return cleaned if cleaned else None
        return None

    def _year(self, paragraphs: list[str], text: str, issue_date: str | None) -> str | None:
        for paragraph in paragraphs[:10]:
            match = YEAR_RE.search(self._normalize(paragraph))
            if match:
                return self._clean(match.group(1))
        if issue_date:
            return issue_date[-4:]
        match = re.search(r"[\d\u0660-\u0669]{4}", text)
        return match.group(0) if match else None

    def _session_number(self, text: str) -> str | None:
        match = SESSION_RE.search(self._normalize(text))
        if not match:
            return None
        value = self._clean(match.group(1))
        if value and " " in value:
            tokens = value.split()
            if "الاعتيادية" in tokens:
                value = " ".join(tokens[tokens.index("الاعتيادية") + 1 :])
            elif len(tokens) > 3:
                value = " ".join(tokens[-2:])
        return value

    def _session_date(self, text: str) -> str | None:
        match = SESSION_RE.search(self._normalize(text))
        return self._clean(match.group(2)) if match else None

    def _subject(self, text: str) -> str | None:
        match = SUBJECT_RE.search(self._normalize(text))
        return self._clean(match.group(1)) if match else None

    def _sender(self, paragraphs: list[str]) -> str | None:
        for paragraph in paragraphs[:6]:
            if paragraph.startswith("وزارة") or "مجلس الوزراء" in paragraph:
                return self._clean(paragraph)
        return None

    def _recipient(self, paragraphs: list[str]) -> str | None:
        for paragraph in paragraphs[:8]:
            normalized = paragraph.strip()
            if normalized.startswith(("إلى", "الى")):
                return self._clean(normalized)
        return None

    def _signature(self, paragraphs: list[str]) -> dict[str, str | None] | None:
        for index, paragraph in enumerate(paragraphs):
            normalized = self._normalize(paragraph)
            if len(normalized) <= 90 and SIGNATURE_TITLE_RE.search(normalized):
                name = self._clean(paragraphs[index - 1]) if index > 0 else None
                title = self._clean(paragraph)
                date = None
                for candidate in paragraphs[index + 1 : index + 4]:
                    match = DATE_RE.search(candidate)
                    if match:
                        date = self._clean(match.group(0))
                        break
                return {"name": name, "title": title, "date": date}
        return None

    def _last_date(self, text: str) -> str | None:
        dates = DATE_RE.findall(text)
        return self._clean(dates[-1]) if dates else None

    def extract_reference_numbers(self, text: str) -> list[str]:
        return list(dict.fromkeys(self._clean(match) for match in BOOK_RE.findall(text) if self._clean(match)))

    def extract_reference_records(self, text: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        normalized = self._normalize(text)
        for match in RECOMMENDATION_NUMBER_RE.findall(normalized):
            value = self._clean(match)
            if value:
                records.append({"type": "recommendation_number", "text": value})
        for match in BOOK_RE.findall(normalized):
            value = self._clean(match)
            if value:
                records.append({"type": "reference_number", "text": value})
        return self._dedupe_records(records)

    def _dedupe_records(self, records: list[dict[str, str]]) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        unique = []
        for record in records:
            key = (record["type"], record["text"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    def _normalize(self, value: str) -> str:
        value = re.sub(r"[\u064b-\u065f\u0670\u0640ـ]+", "", value)
        value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")
        return re.sub(r"\s+", " ", value).strip()

    def _clean(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n:-/،.()")
        return cleaned or None
