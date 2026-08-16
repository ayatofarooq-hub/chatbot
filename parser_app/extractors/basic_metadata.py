"""Deterministic metadata extraction engine."""

from __future__ import annotations

import re
from pathlib import Path

from models.document import CleanedDocument, DocumentMetadata


_DATE_PATTERN = r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}"
_DOC_NUMBER_PATTERN = re.compile(r"\u0631\u0642\u0645\s*\(([^)]*)\)")
_REFERENCE_NUMBER_PATTERN = re.compile(
    r"(?:\u0627\u0644\u0645\u0631\u0642\u0645(?:\u0629)?\s+\u0628\u0627\u0644\u0639\u062f\u062f|\u0627\u0644\u0639\u062f\u062f)\s*\(([^)]*)\)"
)
_SUBJECT_PATTERN = re.compile(
    r"\u0627\u0644\u0645\u0648\u0636[\u0640\s]*\u0648\u0639\s*[/:\-]\s*(.+)"
)
_SESSION_PATTERN = re.compile(
    r"(?:\u0627\u0644\u062c\u0644\u0633\u0629|\u062c\u0644\u0633\u062a\u0647)\s+(.{1,80}?)\s+"
    r"\u0627\u0644\u0645\u0646\u0639\u0642\u062f\u0629\s+"
    r"(?:\u0641\u064a\s+)?(" + _DATE_PATTERN + r")"
)
_DATE = re.compile(_DATE_PATTERN)
_MINISTRY_LINE = re.compile(r"^(\u0648\u0632\u0627\u0631\u0629\s+[^/،\n]+)(?:\s*/\s*(.+))?$")
_SIGNATURE_TITLE = re.compile(
    r"(?:\u0627\u0644\u0623\u0645\u064a\u0646|\u0627\u0644\u0627\u0645\u064a\u0646|"
    r"\u0627\u0644\u0648\u0632\u064a\u0631|"
    r"\u0627\u0644\u0645\u062f\u064a\u0631)"
)
_DISTRIBUTION_MARKER = re.compile(
    r"\u0635[\u0640\s]*\u0648\u0631\u0629\s+\u0639\u0646[\u0640\s]*\u0647\s+"
    r"\u0627?\u0644[\u0640\s]*\u064a"
)
_ATTACHMENTS_MARKER = re.compile(
    r"\u0627\u0644\u0645[\u064f\u0640\s]*\u0631\u0627\u0641\u0642[\u0640\s]*\u0627\u062a"
)


class MetadataExtractor:
    """Extract structured metadata without using a language model."""

    def extract(self, document: CleanedDocument) -> DocumentMetadata:
        paragraphs = document.paragraphs
        raw_text = document.raw_text
        first_line = paragraphs[0] if paragraphs else ""
        ministry, department = self._extract_ministry_department(first_line)

        return DocumentMetadata(
            source_name=document.filename,
            source_path=document.filename,
            stem=Path(document.filename).stem,
            extension=document.extension,
            size_bytes=len(raw_text.encode("utf-8")),
            character_count=len(raw_text),
            line_count=0 if not raw_text else raw_text.count("\n") + 1,
            document_number=self._extract_document_number(raw_text, paragraphs),
            document_year=self._extract_document_year(raw_text, paragraphs),
            issue_date=self._extract_issue_date(paragraphs),
            ministry=ministry,
            department=department,
            subject=self._extract_subject(raw_text),
            session_number=self._extract_session_number(raw_text),
            session_date=self._extract_session_date(raw_text),
            reference_number=self._extract_reference_number(raw_text),
            sender=self._extract_sender(paragraphs, ministry, department),
            recipient=self._extract_recipient(paragraphs),
            signature=self._extract_signature(paragraphs),
            attachments=self._extract_attachments(paragraphs),
            distribution_list=self._extract_distribution_list(paragraphs),
        )

    def _extract_ministry_department(self, first_line: str) -> tuple[str | None, str | None]:
        match = _MINISTRY_LINE.search(first_line)
        if not match:
            return None, None
        return self._clean_value(match.group(1)), self._clean_value(match.group(2))

    def _extract_subject(self, text: str) -> str | None:
        match = _SUBJECT_PATTERN.search(text)
        return self._clean_value(match.group(1)) if match else None

    def _extract_document_number(self, text: str, paragraphs: list[str]) -> str | None:
        for paragraph in paragraphs[:8]:
            if "\u0631\u0642" not in paragraph and "\u0639\u062f\u062f" not in paragraph:
                continue
            match = _DOC_NUMBER_PATTERN.search(paragraph)
            if match:
                value = self._clean_number(match.group(1))
                if value:
                    return value
        return None

    def _extract_document_year(self, text: str, paragraphs: list[str]) -> str | None:
        year_patterns = (
            re.compile(r"\u0644\u0633\u0646[\u0640\s]*\u0629\s*([\d\u0660-\u0669]{4})"),
            re.compile(r"\u0633\u0646[\u0640\s]*\u0629\s*([\d\u0660-\u0669]{4})"),
        )
        for paragraph in paragraphs[:10]:
            normalized = self._normalize_arabic(paragraph)
            for pattern in year_patterns:
                match = pattern.search(normalized)
                if match:
                    return self._clean_value(match.group(1))

        issue_date = self._extract_issue_date(paragraphs)
        if issue_date:
            match = re.search(r"[\d\u0660-\u0669]{4}", issue_date)
            if match:
                return self._clean_value(match.group(0))
        return None

    def _extract_reference_number(self, text: str) -> str | None:
        return self._first_clean_group(_REFERENCE_NUMBER_PATTERN, text)

    def _extract_issue_date(self, paragraphs: list[str]) -> str | None:
        signature_index = self._signature_title_index(paragraphs)
        if signature_index is not None:
            for paragraph in paragraphs[signature_index + 1 : signature_index + 4]:
                match = _DATE.search(paragraph)
                if match:
                    return self._clean_value(match.group(0))

        dates = _DATE.findall("\n".join(paragraphs))
        return self._clean_value(dates[-1]) if dates else None

    def _extract_session_number(self, text: str) -> str | None:
        match = _SESSION_PATTERN.search(self._normalize_arabic(text))
        return self._clean_value(match.group(1)) if match else None

    def _extract_session_date(self, text: str) -> str | None:
        match = _SESSION_PATTERN.search(self._normalize_arabic(text))
        return self._clean_value(match.group(2)) if match else None

    def _extract_sender(
        self,
        paragraphs: list[str],
        ministry: str | None,
        department: str | None,
    ) -> str | None:
        if ministry and department:
            return f"{ministry} / {department}"
        if ministry:
            return ministry

        for paragraph in paragraphs[:5]:
            if "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621" in paragraph:
                return "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621"
        return None

    def _extract_recipient(self, paragraphs: list[str]) -> str | None:
        for paragraph in paragraphs[:8]:
            normalized = paragraph.strip()
            if normalized.startswith("\u0625\u0644\u0649") or normalized.startswith("\u0627\u0644\u0649"):
                return self._clean_value(normalized.split("/", 1)[-1])
        return None

    def _extract_signature(self, paragraphs: list[str]) -> str | None:
        title_index = self._signature_title_index(paragraphs)
        if title_index is None or title_index == 0:
            return None

        name = self._clean_value(paragraphs[title_index - 1])
        title = self._clean_value(paragraphs[title_index])
        if not name:
            return title
        if not title:
            return name
        return f"{name} - {title}"

    def _extract_attachments(self, paragraphs: list[str]) -> list[str]:
        marker_index = self._find_index(paragraphs, _ATTACHMENTS_MARKER)
        if marker_index is None:
            return []

        attachments: list[str] = []
        remaining = paragraphs[marker_index + 1 :]
        for offset, paragraph in enumerate(remaining):
            next_paragraph = remaining[offset + 1] if offset + 1 < len(remaining) else ""
            if self._is_stop_line(paragraph) or self._is_signature_title(next_paragraph):
                break
            value = self._clean_value(paragraph)
            if value:
                attachments.append(value)
        return attachments

    def _extract_distribution_list(self, paragraphs: list[str]) -> list[str]:
        marker_index = self._find_index(paragraphs, _DISTRIBUTION_MARKER)
        if marker_index is None:
            return []

        distribution: list[str] = []
        for paragraph in paragraphs[marker_index + 1 :]:
            if self._looks_like_page_marker(paragraph):
                continue
            if self._looks_like_footer_stamp(paragraph):
                continue
            value = self._clean_value(paragraph)
            if value:
                distribution.append(value)
        return distribution

    def _signature_title_index(self, paragraphs: list[str]) -> int | None:
        for index, paragraph in enumerate(paragraphs):
            if self._is_signature_title(paragraph):
                return index
        return None

    def _find_index(self, paragraphs: list[str], pattern: re.Pattern[str]) -> int | None:
        for index, paragraph in enumerate(paragraphs):
            if pattern.search(self._normalize_arabic(paragraph)):
                return index
        return None

    def _is_stop_line(self, paragraph: str) -> bool:
        return bool(
            self._is_signature_title(paragraph)
            or _DISTRIBUTION_MARKER.search(self._normalize_arabic(paragraph))
            or self._looks_like_page_marker(paragraph)
        )

    def _is_signature_title(self, paragraph: str) -> bool:
        normalized = self._normalize_arabic(paragraph)
        if "/" in normalized or len(normalized) > 90:
            return False
        return bool(_SIGNATURE_TITLE.search(normalized))

    def _looks_like_page_marker(self, paragraph: str) -> bool:
        return bool(re.fullmatch(r"\(?[\d\u0660-\u0669]+\s*-\s*[\d\u0660-\u0669]+\)?", paragraph.strip()))

    def _looks_like_footer_stamp(self, paragraph: str) -> bool:
        normalized = self._normalize_arabic(paragraph)
        return bool(_DATE.search(normalized) and len(normalized) < 80 and normalized.count("/") <= 2)

    def _first_clean_group(self, pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        if not match:
            return None
        return self._clean_number(match.group(1))

    def _clean_number(self, value: str | None) -> str | None:
        cleaned = self._clean_value(value)
        if not cleaned:
            return None
        if not re.search(r"[\d\u0660-\u0669A-Za-z\u0621-\u064a]", cleaned):
            return None
        return cleaned

    def _clean_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value)
        cleaned = cleaned.strip(" \t\r\n:-/،.()")
        return cleaned or None

    def _normalize_arabic(self, value: str) -> str:
        normalized = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
        normalized = normalized.replace("\u0623", "\u0627")
        normalized = normalized.replace("\u0625", "\u0627")
        normalized = normalized.replace("\u0622", "\u0627")
        normalized = normalized.replace("\u0649", "\u064a")
        return normalized
