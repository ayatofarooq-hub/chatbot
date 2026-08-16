"""Legal content extraction component for the standalone parser pipeline."""

import re
from pathlib import Path

from models.document import CleanedDocument, LegalContent


_LEGAL_REFERENCE = re.compile(
    r"(?:\u0642\u0627\u0646\u0648\u0646|\u0642\u0631\u0627\u0631|\u0646\u0638\u0627\u0645|\u062a\u0639\u0644\u064a\u0645\u0627\u062a|\u0627\u0645\u0631|\u0623\u0645\u0631)\s+"
    r"(?:\u0631\u0642\u0645\s+)?[\d\u0660-\u0669]+"
    r"(?:\s+\u0644\u0633\u0646\u0629\s+[\d\u0660-\u0669]+)?"
)


class LegalContentExtractor:
    """Extract legal content from cleaned text without external chatbot logic."""

    def extract(self, document: CleanedDocument) -> LegalContent:
        paragraphs = document.paragraphs
        title = paragraphs[0] if paragraphs else Path(document.filename).stem
        references = sorted(set(_LEGAL_REFERENCE.findall(document.raw_text)))

        return LegalContent(
            title=title,
            body=document.raw_text,
            paragraphs=paragraphs,
            legal_references=references,
        )
