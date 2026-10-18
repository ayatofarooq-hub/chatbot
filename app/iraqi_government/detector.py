"""Document type detection for Iraqi government legal documents."""

from __future__ import annotations

from app.iraqi_government.models import DocumentType


TYPE_KEYWORDS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    ("amendment", ("تعديل", "قانون التعديل", "تعديل قانون")),
    ("law", ("قانون", "قانون رقم", "باسم الشعب", "رئاسة الجمهورية")),
    ("decision", ("قرار مجلس الوزراء", "قرار رقم", "قرر مجلس الوزراء", "قرار")),
    ("regulation", ("نظام", "النظام", "نظام رقم")),
    ("instruction", ("تعليمات", "تعليمات رقم")),
    ("order", ("امر ديواني", "أمر ديواني", "امر وزاري", "أمر وزاري")),
    ("decree", ("مرسوم جمهوري", "مرسوم")),
)


def detect_document_type(text: str, filename: str = "") -> DocumentType:
    """Detect the most likely Iraqi legal document type from text and filename."""

    haystack = f"{filename}\n{text[:3000]}".lower()
    for document_type, keywords in TYPE_KEYWORDS:
        if any(keyword.lower() in haystack for keyword in keywords):
            return document_type
    return "unknown"
