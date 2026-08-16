"""Rule-based metadata extraction for legal documents."""

from __future__ import annotations

import re
from typing import Any


def extract_metadata(text: str) -> dict[str, Any]:
    """Extract deterministic metadata fields from legal document text."""

    normalized = text or ""
    metadata: dict[str, Any] = {}

    patterns = {
        "document_number": [
            r"document\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)",
            r"doc\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)",
        ],
        "decision_number": [r"decision\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)", r"decision\s*number\s*[:#-]?\s*([A-Za-z0-9/\-]+)"],
        "decision_year": [r"decision\s*year\s*[:#-]?\s*(\d{4})", r"for\s*the\s*year\s*(\d{4})"],
        "letter_number": [r"letter\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)", r"letter\s*number\s*[:#-]?\s*([A-Za-z0-9/\-]+)"],
        "issue_date": [r"issue\s*date\s*[:#-]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})", r"dated\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})"],
        "cabinet_session_number": [r"cabinet\s*session\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)", r"session\s*no\.?\s*[:#-]?\s*([A-Za-z0-9/\-]+)"],
        "cabinet_session_date": [r"cabinet\s*session\s*date\s*[:#-]?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})"],
        "ministry": [r"ministry\s*[:#-]?\s*([A-Za-z\s]+?)(?:\n|$)", r"for\s+the\s+ministry\s+of\s+([A-Za-z\s]+?)(?:\n|$)"],
        "department": [r"department\s*[:#-]?\s*([A-Za-z\s]+?)(?:\n|$)", r"directorate\s*[:#-]?\s*([A-Za-z\s]+?)(?:\n|$)"],
        "subject": [r"subject\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)", r"title\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)"],
        "sender": [r"from\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)", r"sender\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)"],
        "recipient": [r"to\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)", r"recipient\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)"],
        "signature": [r"signature\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)", r"signed\s+by\s+([A-Za-z0-9/\-\s]+?)(?:\n|$)"],
        "attachments": [r"attachments\s*[:#-]?\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)", r"attached\s*([A-Za-z0-9/\-\s]+?)(?:\n|$)"],
        "distribution_list": [r"distribution\s*list\s*[:#-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)", r"cc\s*[:#-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)"],
        "reference_documents": [r"reference\s*documents\s*[:#-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)", r"references\s*[:#-]?\s*([A-Za-z0-9,/\-\s]+?)(?:\n|$)"],
    }

    for field_name, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if value:
                    metadata[field_name] = re.sub(r"\s+", " ", value)
                    break

    if "subject" not in metadata and re.search(r"\bsubject\b", normalized, flags=re.IGNORECASE):
        metadata["subject"] = ""

    return metadata
