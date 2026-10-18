"""Compatibility entrypoint for line-oriented extraction cleanup."""

from app.classifiers.document_cleaner import clean_document_text


def clean_text(text: str) -> str:
    """Remove extraction artifacts and empty lines without rewriting text."""
    return "\n".join(line for line in clean_document_text(text).splitlines() if line.strip())
