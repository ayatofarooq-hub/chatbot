"""Heuristic classifier for legal document categories."""

from __future__ import annotations

import re
from typing import Iterable

SUPPORTED_CATEGORIES = [
    "Cabinet Decision",
    "Ministry Letter",
    "Recommendation",
    "Official Correspondence",
    "Committee Formation",
    "Circular",
    "Administrative Letter",
]


def classify_document_type(text: str, categories: Iterable[str] | None = None) -> tuple[str | None, float, str]:
    """Classify a document into one of the supported legal categories.

    The classifier uses surface patterns from the document text and falls back to a
    neutral result when no strong signal is found.
    """

    normalized = "\n".join(text.lower().splitlines())
    candidates = list(categories or SUPPORTED_CATEGORIES)

    if not normalized.strip():
        return None, 0.0, "empty document"

    signals = {
        "Cabinet Decision": [r"\bcabinet\b", r"\bdecision\b", r"\bministerial council\b"],
        "Ministry Letter": [r"\bministry\b", r"\bletter\b", r"\boffice\b"],
        "Recommendation": [r"\brecommendation\b", r"\brecommended\b", r"\bproposal\b"],
        "Official Correspondence": [r"\bofficial correspondence\b", r"\bcorrespondence\b", r"\bmemorandum\b"],
        "Committee Formation": [r"\bcommittee\b", r"\bformation\b", r"\bformed\b"],
        "Circular": [r"\bcircular\b", r"\bnotice\b", r"\bannouncement\b"],
        "Administrative Letter": [r"\badministrative\b", r"\badministration\b", r"\bletter\b"],
    }

    scores: list[tuple[str, float]] = []
    for category in candidates:
        score = 0.0
        for pattern in signals.get(category, []):
            if re.search(pattern, normalized):
                score += 1.0
        if category.lower() in normalized:
            score += 0.25
        if score > 0:
            scores.append((category, score))

    if not scores:
        return None, 0.0, "no category patterns matched"

    best_category, best_score = max(scores, key=lambda item: item[1])
    confidence = min(1.0, best_score / max(1.0, len(signals.get(best_category, []))))
    reason = f"matched {int(best_score)} structural signal(s)"
    return best_category, confidence, reason
