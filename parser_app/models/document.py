"""Well-defined handoff objects for the standalone parser pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Table:
    rows: list[list[str]]


@dataclass(frozen=True)
class Document:
    filename: str
    extension: str
    pages: list[str]
    paragraphs: list[str]
    tables: list[Table]
    raw_text: str


@dataclass(frozen=True)
class CleanedDocument:
    filename: str
    extension: str
    pages: list[str]
    paragraphs: list[str]
    tables: list[Table]
    raw_text: str


@dataclass(frozen=True)
class DocumentTypeDetection:
    document_type: str
    confidence: float
    method: str
    matched_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentMetadata:
    source_name: str
    source_path: str
    stem: str
    extension: str
    size_bytes: int
    character_count: int
    line_count: int
    document_number: str | None = None
    document_year: str | None = None
    issue_date: str | None = None
    ministry: str | None = None
    department: str | None = None
    subject: str | None = None
    session_number: str | None = None
    session_date: str | None = None
    reference_number: str | None = None
    sender: str | None = None
    recipient: str | None = None
    signature: str | None = None
    attachments: list[str] = field(default_factory=list)
    distribution_list: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LegalContent:
    title: str
    body: str
    paragraphs: list[str] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    section_items: list[dict[str, Any]] = field(default_factory=list)
    legal_entities: dict[str, list[str]] = field(default_factory=dict)
    references: dict[str, list[str]] = field(default_factory=dict)
    extracted_fields: dict[str, list[str]] = field(default_factory=dict)
    legal_references: list[str] = field(default_factory=list)
    legal_objective: str | None = None
    executive_summary: str | None = None
    implementation_responsibilities: list[str] = field(default_factory=list)
    decision_outcome: str | None = None
    affected_entities: list[str] = field(default_factory=list)
    extraction_sources: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmLegalAnalysis:
    legal_meaning: str | None = None
    legal_entities: list[dict[str, Any]] = field(default_factory=list)
    structured_fields: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class ParserJson:
    schema_version: str
    created_at: str
    metadata: DocumentMetadata
    document_type: DocumentTypeDetection
    legal_content: LegalContent
    llm_analysis: LlmLegalAnalysis | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {
                "filename": self.metadata.source_name,
                "extension": self.metadata.extension,
                "character_count": self.metadata.character_count,
                "line_count": self.metadata.line_count,
            },
            "document": {
                "type": self.document_type.document_type,
                "number": self.metadata.document_number,
                "year": self.metadata.document_year,
                "issue_date": self.metadata.issue_date,
                "session": {
                    "number": self.metadata.session_number,
                    "date": self.metadata.session_date,
                },
                "title": self.legal_content.title,
                "subject": self.metadata.subject,
                "reference_number": self.metadata.reference_number,
                "sender": self.metadata.sender,
                "recipient": self.metadata.recipient,
                "signature": self.metadata.signature,
                "attachments": self.metadata.attachments,
            },
            "metadata": {
                "document_number": self.metadata.document_number,
                "document_year": self.metadata.document_year,
                "issue_date": self.metadata.issue_date,
                "ministry": self.metadata.ministry,
                "department": self.metadata.department,
                "subject": self.metadata.subject,
                "session_number": self.metadata.session_number,
                "session_date": self.metadata.session_date,
                "reference_number": self.metadata.reference_number,
                "sender": self.metadata.sender,
                "recipient": self.metadata.recipient,
                "signature": self.metadata.signature,
                "attachments": self.metadata.attachments,
                "distribution_list": self.metadata.distribution_list,
            },
            "references": self._reference_items(),
            "decision": {
                "sections": self.legal_content.section_items,
            },
            "body": self.legal_content.body,
            "paragraphs": self.legal_content.paragraphs,
            "legal_entities": self.legal_content.legal_entities,
            "extracted_fields": self.legal_content.extracted_fields,
            "signature": self._signature_object(),
        }

    def _reference_items(self) -> list[dict[str, str]]:
        labels = {
            "decision_numbers": "Decision Number",
            "book_numbers": "Book Number",
            "law_numbers": "Law Number",
            "article_numbers": "Article Number",
            "recommendation_numbers": "Recommendation Number",
        }
        references: list[dict[str, str]] = []
        for key, label in labels.items():
            for value in self.legal_content.references.get(key, []):
                references.append({"type": label, "text": value})
        return references

    def _signature_object(self) -> dict[str, str | None]:
        if not self.metadata.signature:
            return {"text": None, "name": None, "title": None}
        name, separator, title = self.metadata.signature.partition(" - ")
        return {
            "text": self.metadata.signature,
            "name": name.strip() or None,
            "title": title.strip() if separator and title.strip() else None,
        }
