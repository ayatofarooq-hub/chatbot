"""Metadata and legal content extraction for Iraqi government documents."""

from __future__ import annotations

import re

from app.iraqi_government.detector import detect_document_type
from app.iraqi_government.models import GovernmentMetadata, LegalArticle, LegalContent


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUMBER = r"([0-9٠-٩۰-۹]+)"
YEAR = r"([12][0-9]{3}|[٠-٩۰-۹]{4})"
DATE = r"([0-9٠-٩۰-۹]{1,2}\s*[/-]\s*[0-9٠-٩۰-۹]{1,2}\s*[/-]\s*[0-9٠-٩۰-۹]{4})"

NUMBER_PATTERNS = {
    "law": re.compile(r"قانون(?:\s+\S+){0,4}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "decision": re.compile(r"قرار(?:\s+\S+){0,5}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "regulation": re.compile(r"نظام(?:\s+\S+){0,4}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "instruction": re.compile(r"تعليمات(?:\s+\S+){0,4}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "order": re.compile(r"(?:امر|أمر)(?:\s+\S+){0,4}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "decree": re.compile(r"مرسوم(?:\s+\S+){0,4}?\s+رقم\s*\(?%s\)?" % NUMBER),
    "amendment": re.compile(r"(?:تعديل|قانون التعديل)(?:\s+\S+){0,5}?\s+رقم\s*\(?%s\)?" % NUMBER),
}
YEAR_PATTERN = re.compile(r"(?:لسنة|سنة|لعام|عام)\s*%s" % YEAR)
GAZETTE_PATTERN = re.compile(r"(?:الوقائع العراقية|جريدة الوقائع العراقية)(?:\s+بالعدد)?\s*%s?" % NUMBER)
AUTHORITY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("مجلس الوزراء", re.compile(r"مجلس الوزراء")),
    ("رئاسة الجمهورية", re.compile(r"رئاسة الجمهورية|رئيس الجمهورية")),
    ("مجلس النواب", re.compile(r"مجلس النواب")),
    ("وزارة", re.compile(r"وزارة\s+[\u0600-\u06ff\s]+")),
    ("الأمانة العامة لمجلس الوزراء", re.compile(r"الأمانة العامة لمجلس الوزراء")),
)
ARTICLE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:المادة|مادة)\s*(?:\(|\s)?([0-9٠-٩۰-۹]+|[اأإآء-ي]+)(?:\)|\s|:|-)*(.*?)(?=(?:\n\s*(?:المادة|مادة)\s*(?:\(|\s)?(?:[0-9٠-٩۰-۹]+|[اأإآء-ي]+))|\Z)",
    re.DOTALL,
)


def extract_fixed_metadata(text: str, filename: str = "") -> GovernmentMetadata:
    """Extract standardized fixed metadata using deterministic patterns."""

    document_type = detect_document_type(text, filename)
    title = _extract_title(text, filename)
    number = _extract_document_number(text, document_type)
    year = _first_match(YEAR_PATTERN, text)
    dates = _unique(DATE, text)
    gazette_match = GAZETTE_PATTERN.search(text)
    gazette_issue = _normalize_digits(gazette_match.group(1)) if gazette_match and gazette_match.group(1) else None

    return GovernmentMetadata(
        title=title,
        document_type=document_type,
        document_number=_normalize_digits(number) if number else None,
        year=_normalize_digits(year) if year else None,
        issuing_authority=_extract_authority(text),
        publication_date=_normalize_digits(dates[0]) if dates else None,
        effective_date=_normalize_digits(dates[1]) if len(dates) > 1 else None,
        gazette_name="الوقائع العراقية" if gazette_match else None,
        gazette_issue=gazette_issue,
        status="active" if "نافذ" in text or document_type != "unknown" else "unknown",
    )


def extract_legal_content(text: str) -> LegalContent:
    """Extract preamble, articles, and free-form clauses from legal text."""

    articles: list[LegalArticle] = []
    first_article_start: int | None = None
    for match in ARTICLE_PATTERN.finditer(text):
        if first_article_start is None:
            first_article_start = match.start()
        number = _normalize_digits(match.group(1).strip())
        body = match.group(2).strip(" \n:-")
        title, article_text = _split_title_and_body(body)
        if article_text:
            articles.append(LegalArticle(number=number, title=title, text=article_text))

    preamble = text[:first_article_start].strip() if first_article_start is not None else _first_paragraph(text)
    clauses = [line for line in _non_empty_lines(text) if _looks_like_clause(line)]
    return LegalContent(
        preamble=preamble,
        articles=articles,
        clauses=clauses,
        full_text=text,
    )


def _extract_title(text: str, filename: str) -> str:
    for line in _non_empty_lines(text):
        if len(line) > 250:
            continue
        if any(keyword in line for keyword in ("قانون", "قرار", "نظام", "تعليمات", "أمر", "امر", "مرسوم", "تعديل")):
            return line
    return filename.rsplit(".", 1)[0] if filename else "Untitled Iraqi government document"


def _extract_document_number(text: str, document_type: str) -> str | None:
    pattern = NUMBER_PATTERNS.get(document_type)
    if pattern:
        match = pattern.search(text)
        if match:
            return match.group(1)
    generic = re.search(r"رقم\s*\(?%s\)?" % NUMBER, text)
    return generic.group(1) if generic else None


def _extract_authority(text: str) -> str | None:
    for authority, pattern in AUTHORITY_PATTERNS:
        match = pattern.search(text)
        if match and authority == "وزارة":
            return " ".join(match.group(0).split())
        if match:
            return authority
    return None


def _split_title_and_body(text: str) -> tuple[str | None, str]:
    lines = _non_empty_lines(text)
    if not lines:
        return None, ""
    first = lines[0]
    if len(lines) > 1 and len(first) <= 90 and not first.endswith((".", "،", ";", "؛")):
        return first, "\n".join(lines[1:]).strip()
    return None, "\n".join(lines).strip()


def _first_paragraph(text: str) -> str:
    for paragraph in re.split(r"\n\s*\n", text):
        if paragraph.strip():
            return paragraph.strip()
    return ""


def _looks_like_clause(line: str) -> bool:
    return bool(re.match(r"^(?:[0-9٠-٩۰-۹]+[.)-]|[أ-ي]+[.)-]|اولاً|أولاً|ثانياً|ثالثاً|رابعاً)", line))


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def _unique(pattern: str, text: str) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for value in re.findall(pattern, text):
        normalized = _normalize_digits(value.strip())
        if normalized and normalized not in seen:
            seen.add(normalized)
            values.append(normalized)
    return values


def _normalize_digits(value: str) -> str:
    return value.translate(ARABIC_DIGITS)
