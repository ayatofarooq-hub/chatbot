"""Extract simple legal metadata using regular expressions only."""

from dataclasses import dataclass, field
import re

from app.schemas import DocumentModel


@dataclass
class RegexMetadata:
    decision_numbers: list[str] = field(default_factory=list)
    law_numbers: list[str] = field(default_factory=list)
    years: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    article_numbers: list[str] = field(default_factory=list)


DECISION_NUMBER_PATTERN = re.compile(r"(?:رقم\s+القرار|قرار\s+رقم)\s*[:：]?\s*\(?([0-9٠-٩]+)\)?")
LAW_NUMBER_PATTERN = re.compile(r"(?:رقم\s+القانون|قانون\s+رقم)\s*[:：]?\s*\(?([0-9٠-٩]+)\)?")
YEAR_PATTERN = re.compile(r"(?:لسنة|سنة|عام)\s*([12][0-9]{3}|[١٢][٠-٩]{3})")
DATE_PATTERN = re.compile(
    r"([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4}|"
    r"[0-9٠-٩]{1,2}\s*-\s*[0-9٠-٩]{1,2}\s*-\s*[0-9٠-٩]{4})"
)
ARTICLE_NUMBER_PATTERN = re.compile(r"(?:رقم\s+المادة|مادة|المادة)\s*[:：]?\s*\(?([0-9٠-٩]+)\)?")


def unique_in_order(values: list[str]) -> list[str]:
    """Return values without duplicates while preserving first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_values.append(normalized)
    return unique_values


def extract_regex_metadata_from_text(text: str) -> RegexMetadata:
    """Extract simple metadata from text using regex patterns only."""

    return RegexMetadata(
        decision_numbers=unique_in_order(DECISION_NUMBER_PATTERN.findall(text)),
        law_numbers=unique_in_order(LAW_NUMBER_PATTERN.findall(text)),
        years=unique_in_order(YEAR_PATTERN.findall(text)),
        dates=unique_in_order(DATE_PATTERN.findall(text)),
        article_numbers=unique_in_order(ARTICLE_NUMBER_PATTERN.findall(text)),
    )


def extract_regex_metadata(document: DocumentModel) -> RegexMetadata:
    """Extract simple metadata from a document model using regex patterns only."""

    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return extract_regex_metadata_from_text(text)
