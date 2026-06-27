"""Classify Iraqi legal documents as laws or decisions."""

from __future__ import annotations

import re


LAW = "قانون"
DECISION = "قرار"

LAW_SIGNALS = (
    (re.compile(r"\bقانون\b"), 4),
    (re.compile(r"قانون\s+رقم\s*[\(\[]?[0-9\u0660-\u0669]+"), 5),
    (re.compile(r"لسنة\s*[0-9\u0660-\u0669]{4}"), 3),
    (re.compile(r"\bالمادة\b|\bمادة\b"), 3),
    (re.compile(r"\bالباب\b|\bالفصل\b|\bالقسم\b|\bالفرع\b"), 2),
    (re.compile(r"الأسباب\s+الموجبة"), 4),
    (re.compile(r"ينفذ\s+هذا\s+القانون|ينشر\s+في\s+الجريدة\s+الرسمية"), 5),
)

DECISION_SIGNALS = (
    (re.compile(r"\bقرار\b"), 4),
    (re.compile(r"محكمة|القضاء|التمييز|الاتحادية"), 4),
    (re.compile(r"الدعوى|الطعن|المميز|المميز\s+عليه"), 4),
    (re.compile(r"الحكم|حكمت|قرر(?:ت)?\s+المحكمة"), 3),
    (re.compile(r"العدد\s*[:/]|رقم\s+الدعوى"), 3),
    (re.compile(r"المدعي|المدعى\s+عليه|المتهم|المحكوم"), 2),
)


def score_signals(text: str, signals: tuple[tuple[re.Pattern[str], int], ...]) -> int:
    """Return a weighted score for matched regex signals."""

    score = 0
    for pattern, weight in signals:
        matches = pattern.findall(text)
        if matches:
            score += weight * min(len(matches), 5)
    return score


def classify_document(text: str) -> tuple[str, dict[str, int]]:
    """Classify text as قانون or قرار with signal scores."""

    normalized = re.sub(r"\s+", " ", text or "").strip()
    law_score = score_signals(normalized, LAW_SIGNALS)
    decision_score = score_signals(normalized, DECISION_SIGNALS)
    document_type = DECISION if decision_score > law_score else LAW
    return document_type, {
        "law_score": law_score,
        "decision_score": decision_score,
    }
