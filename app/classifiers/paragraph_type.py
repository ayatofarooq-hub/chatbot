"""Classify DOCX paragraph text."""

from typing import Literal


ParagraphType = Literal["Heading", "Paragraph"]

HEADING_PREFIXES = (
    "باب",
    "الباب",
    "فصل",
    "الفصل",
    "مادة",
    "المادة",
)


def classify_paragraph(text: str) -> ParagraphType:
    """Classify a paragraph as a heading or regular paragraph."""

    stripped = text.strip()
    if stripped.startswith(HEADING_PREFIXES):
        return "Heading"

    return "Paragraph"
