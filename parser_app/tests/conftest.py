"""Shared test helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from builders.document_builder import JsonBuilder
from models.document import DocumentMetadata, DocumentTypeDetection, LegalContent


def sample_metadata(**overrides):
    values = {
        "source_name": "document1.docx",
        "source_path": "document1.docx",
        "stem": "document1",
        "extension": ".docx",
        "size_bytes": 100,
        "character_count": 80,
        "line_count": 4,
        "document_number": "245",
        "document_year": "2024",
        "issue_date": "31/12/2024",
        "ministry": "وزارة الصحة",
        "department": "مكتب الوزير",
        "subject": "تأليف لجنة لدراسة المطالب",
        "session_number": "الاعتيادية الثالثة",
        "session_date": "30/12/2024",
        "reference_number": "245",
        "sender": "وزارة الصحة / مكتب الوزير",
        "recipient": None,
        "signature": "د. مثال - الأمين العام",
        "attachments": [],
        "distribution_list": [],
    }
    values.update(overrides)
    return DocumentMetadata(**values)


def sample_document_type(**overrides):
    values = {
        "document_type": "Cabinet Decision",
        "confidence": 0.94,
        "method": "rule",
        "matched_rules": ["cabinet_decision_terms"],
    }
    values.update(overrides)
    return DocumentTypeDetection(**values)


def sample_legal_content(**overrides):
    values = {
        "title": "قرار مجلس الوزراء",
        "body": "قرار مجلس الوزراء رقم 245 لسنة 2024\nأولا: الموافقة على الطلب.",
        "paragraphs": ["قرار مجلس الوزراء رقم 245 لسنة 2024", "أولا: الموافقة على الطلب."],
        "items": [
            {
                "id": 1,
                "type": "Decision",
                "text": "قرار مجلس الوزراء رقم 245 لسنة 2024",
                "summary": None,
            },
            {
                "id": 2,
                "type": "Approval",
                "text": "أولا: الموافقة على الطلب.",
                "summary": None,
            },
        ],
        "section_items": [
            {
                "id": 1,
                "text": "قرار مجلس الوزراء رقم 245 لسنة 2024",
                "entities": [],
                "money": [],
                "dates": [],
                "references": ["قرار مجلس الوزراء رقم 245"],
            },
            {
                "id": 2,
                "text": "أولا: الموافقة على الطلب.",
                "entities": [],
                "money": [],
                "dates": [],
                "references": [],
            },
        ],
        "legal_entities": {
            "ministries": ["وزارة الصحة"],
            "companies": [],
            "committees": [],
            "authorities": [],
            "government_offices": ["مكتب الوزير"],
            "people": ["د. مثال"],
            "projects": [],
            "councils": ["مجلس الوزراء"],
        },
        "references": {
            "decision_numbers": ["قرار مجلس الوزراء رقم 245"],
            "book_numbers": [],
            "law_numbers": [],
            "article_numbers": [],
            "recommendation_numbers": [],
        },
        "extracted_fields": {
            "money": [],
            "percentages": [],
            "years": ["2024"],
            "durations": [],
            "pipe_lengths": [],
            "diameters": [],
            "thickness": [],
            "quantities": [],
        },
        "legal_references": ["قرار مجلس الوزراء رقم 245"],
        "legal_objective": "تأليف لجنة لدراسة المطالب",
        "executive_summary": None,
        "implementation_responsibilities": ["تتحمل وزارة الصحة سلامة الإجراءات."],
        "decision_outcome": "أولا: الموافقة على الطلب.",
        "affected_entities": ["وزارة الصحة"],
        "extraction_sources": {"legal_objective": "metadata"},
    }
    values.update(overrides)
    return LegalContent(**values)


def sample_parser_json(**overrides):
    document = JsonBuilder().build(
        sample_metadata(),
        sample_document_type(),
        sample_legal_content(),
        overrides.pop("llm_analysis", None),
    )
    if not overrides:
        return document
    values = {
        "schema_version": document.schema_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": document.metadata,
        "document_type": document.document_type,
        "legal_content": document.legal_content,
        "llm_analysis": document.llm_analysis,
    }
    values.update(overrides)
    return type(document)(**values)
