"""Cleaning utilities for legal documents while preserving meaning."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any


def clean_document_text(text: str) -> str:
    """Normalize document text while preserving legal structure and semantics."""

    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\uFFFD", "")
    text = re.sub(r"[\t\u00a0]+", " ", text)

    pages = [page for page in text.split("\f") if page.strip()]
    if not pages:
        pages = [text]

    repeated_artifacts = _repeated_page_edge_lines(pages)

    cleaned_lines: list[str] = []
    for raw_line in text.replace("\f", "\n").split("\n"):
        line = re.sub(r"[^\S\n]+", " ", raw_line).strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        if _is_page_number(line) or line in repeated_artifacts:
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"(?<!\n)\n(?!\n)", "\n", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\d)\s+(?=\d{4}[-/]\d{1,2}[-/]\d{1,2})", " ", cleaned)
    cleaned = re.sub(r"(?<=\d)\s+(?=\d)", " ", cleaned)
    cleaned = cleaned.strip()
    return cleaned


def _is_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"(?:page|صفحة)\s*[0-9٠-٩]+", line, flags=re.IGNORECASE))


def _repeated_page_edge_lines(pages: list[str]) -> set[str]:
    if len(pages) < 3:
        return set()

    candidates: list[str] = []
    for page in pages:
        lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in page.splitlines() if line.strip()]
        candidates.extend(lines[:3])
        candidates.extend(lines[-2:])

    counts = Counter(candidates)
    threshold = max(2, len(pages) // 2 + 1)
    return {line for line, count in counts.items() if count >= threshold and not _is_page_number(line)}
