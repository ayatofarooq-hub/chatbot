"""Data models for Iraqi government document preprocessing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DocumentType = Literal[
    "law",
    "decision",
    "regulation",
    "instruction",
    "order",
    "decree",
    "amendment",
    "unknown",
]


@dataclass(frozen=True)
class LoadedGovernmentDocument:
    """Raw document text loaded from disk."""

    source_path: str
    source_file: str
    filename: str
    extension: str
    text: str
    loader_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernmentMetadata:
    """Fixed metadata fields extracted from the legal text."""

    title: str
    document_type: DocumentType
    document_number: str | None = None
    year: str | None = None
    issuing_authority: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    gazette_name: str | None = None
    gazette_issue: str | None = None
    country: str = "Iraq"
    language: str = "Arabic"
    status: str = "unknown"


@dataclass(frozen=True)
class LegalArticle:
    """One extracted legal content unit."""

    number: str | None
    title: str | None
    text: str


@dataclass(frozen=True)
class LegalContent:
    """Legal body extracted from the source text."""

    preamble: str
    articles: list[LegalArticle]
    clauses: list[str]
    full_text: str


@dataclass(frozen=True)
class ValidationResult:
    """Validation result for standardized JSON."""

    valid: bool
    errors: list[str] = field(default_factory=list)
