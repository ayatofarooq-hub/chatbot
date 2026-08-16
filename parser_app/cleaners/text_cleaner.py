"""Text cleaning engine that preserves legal meaning.

The cleaner removes document artifacts only. It does not summarize, paraphrase,
or rewrite legal content.
"""

from __future__ import annotations

from collections import Counter
import re

from models.document import CleanedDocument, Document, Table


_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)
_INLINE_SPACES = re.compile(r"[ \t]{2,}")
_DATE_PATTERN = re.compile(r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}")
_PAGE_COUNTER = re.compile(r"^\(?\s*[\d\u0660-\u0669]+\s*[-/]\s*[\d\u0660-\u0669]+\s*\)?$")
_PAGE_WORD_COUNTER = re.compile(
    r"^(?:page|صفحة|ص)\s*[\d\u0660-\u0669]+\s*(?:of|من|/|-)\s*[\d\u0660-\u0669]+$",
    re.IGNORECASE,
)
_FOOTER_STAMP = re.compile(
    r"^[\u0621-\u064aA-Za-z]{2,20}\s+"
    r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}"
    r"(?:\s*\(?\s*[\d\u0660-\u0669]+\s*[-/]\s*[\d\u0660-\u0669]+\s*\)?\s*)+$"
)
_FOOTER_STAMP_CHUNKS = re.compile(
    r"^(?:[\u0621-\u064aA-Za-z]{2,20}\s+"
    r"[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{1,2}\s*/\s*[\d\u0660-\u0669]{4}"
    r"\s*\(?\s*[\d\u0660-\u0669]+\s*[-/]\s*[\d\u0660-\u0669]+\s*\)?\s*)+$"
)
_ARABIC_DIACRITICS_AND_TATWEEL = re.compile(r"[\u064b-\u065f\u0670\u0640]")


def clean_text(text: str) -> str:
    """Normalize whitespace without changing document wording."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _TRAILING_SPACES.sub("", normalized)
    normalized = "\n".join(_clean_line_spacing(line) for line in normalized.split("\n"))
    normalized = _MULTIPLE_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()


def _clean_line_spacing(line: str) -> str:
    return _INLINE_SPACES.sub(" ", line).strip()


def _clean_table(table: Table) -> Table:
    return Table(rows=[[clean_text(cell) for cell in row] for row in table.rows])


class DocumentCleaner:
    """Clean a generic Document and return a CleanedDocument object."""

    def clean(self, document: Document) -> CleanedDocument:
        repeated_artifacts = self._repeated_page_artifacts(document.pages)
        cleaned_pages = self._clean_pages(document.pages, repeated_artifacts)
        cleaned_paragraphs = self._clean_paragraphs(document.paragraphs, repeated_artifacts)

        if cleaned_pages:
            raw_text = "\n".join(cleaned_pages)
        else:
            raw_text = "\n".join(cleaned_paragraphs)

        return CleanedDocument(
            filename=document.filename,
            extension=document.extension,
            pages=cleaned_pages,
            paragraphs=cleaned_paragraphs,
            tables=[_clean_table(table) for table in document.tables],
            raw_text=clean_text(raw_text),
        )

    def _clean_pages(self, pages: list[str], repeated_artifacts: set[str]) -> list[str]:
        cleaned_pages: list[str] = []
        for page in pages:
            cleaned_lines = self._clean_lines(page.splitlines(), repeated_artifacts)
            if cleaned_lines:
                cleaned_pages.append("\n".join(cleaned_lines))
        return cleaned_pages

    def _clean_paragraphs(self, paragraphs: list[str], repeated_artifacts: set[str]) -> list[str]:
        cleaned: list[str] = []
        previous_key: str | None = None

        for paragraph in paragraphs:
            value = clean_text(paragraph)
            if not value:
                continue
            if self._is_page_artifact(value, repeated_artifacts):
                continue

            key = self._normalized_key(value)
            if key == previous_key and self._is_safe_duplicate_artifact(value):
                continue

            cleaned.append(value)
            previous_key = key

        return cleaned

    def _clean_lines(self, lines: list[str], repeated_artifacts: set[str]) -> list[str]:
        cleaned: list[str] = []
        previous_key: str | None = None

        for line in lines:
            value = clean_text(line)
            if not value:
                continue
            if self._is_page_artifact(value, repeated_artifacts):
                continue

            key = self._normalized_key(value)
            if key == previous_key and self._is_safe_duplicate_artifact(value):
                continue

            cleaned.append(value)
            previous_key = key

        return cleaned

    def _repeated_page_artifacts(self, pages: list[str]) -> set[str]:
        if len(pages) < 2:
            return set()

        candidates: list[str] = []
        for page in pages:
            lines = [clean_text(line) for line in page.splitlines() if clean_text(line)]
            edge_lines = lines[:3] + lines[-3:]
            candidates.extend(self._normalized_key(line) for line in edge_lines)

        counts = Counter(candidates)
        minimum_repeats = max(2, len(pages) // 2)
        return {key for key, count in counts.items() if count >= minimum_repeats}

    def _is_page_artifact(self, value: str, repeated_artifacts: set[str]) -> bool:
        key = self._normalized_key(value)
        return bool(
            key in repeated_artifacts
            or _PAGE_COUNTER.fullmatch(value)
            or _PAGE_WORD_COUNTER.fullmatch(value)
            or self._looks_like_footer_stamp(value)
        )

    def _is_safe_duplicate_artifact(self, value: str) -> bool:
        normalized = self._normalize_arabic(value)
        if self._contains_legal_reference(normalized):
            return False
        if self._contains_monetary_value(normalized):
            return False
        if self._contains_article_number(normalized):
            return False
        if self._starts_with_numbering(normalized):
            return False
        return len(normalized) <= 120

    def _looks_like_footer_stamp(self, value: str) -> bool:
        normalized = self._normalize_arabic(value)
        if _FOOTER_STAMP_CHUNKS.fullmatch(normalized):
            return True
        if not _FOOTER_STAMP.fullmatch(normalized):
            return False
        return normalized.count("/") <= 4

    def _contains_legal_reference(self, value: str) -> bool:
        return any(
            marker in value
            for marker in (
                "قانون",
                "قرار",
                "نظام",
                "تعليمات",
                "مجلس الوزراء",
                "المادة",
            )
        )

    def _contains_monetary_value(self, value: str) -> bool:
        return any(marker in value for marker in ("دينار", "دولار", "$", "€", "£"))

    def _contains_article_number(self, value: str) -> bool:
        return bool(re.search(r"\b(?:المادة|مادة)\s*\(?\s*[\d\u0660-\u0669]+", value))

    def _starts_with_numbering(self, value: str) -> bool:
        return bool(
            re.match(
                r"^\s*(?:[\d\u0660-\u0669]+[\).-]|[أإا]ولا|ثانيا|ثالثا|رابعا|خامسا|[-*•])",
                value,
            )
        )

    def _normalized_key(self, value: str) -> str:
        return re.sub(r"\s+", " ", self._normalize_arabic(value)).strip()

    def _normalize_arabic(self, value: str) -> str:
        normalized = _ARABIC_DIACRITICS_AND_TATWEEL.sub("", value)
        normalized = normalized.replace("\u0623", "\u0627")
        normalized = normalized.replace("\u0625", "\u0627")
        normalized = normalized.replace("\u0622", "\u0627")
        normalized = normalized.replace("\u0649", "\u064a")
        return normalized
