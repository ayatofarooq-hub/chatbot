"""Rule-first Iraqi government document type detector."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from config import DOCUMENT_TYPE_CONFIDENCE_THRESHOLD
from models.document import CleanedDocument, DocumentTypeDetection


class LlmDocumentClassifier(Protocol):
    def classify(self, document: CleanedDocument) -> DocumentTypeDetection:
        """Classify a document when rules are not confident enough."""


@dataclass(frozen=True)
class _Rule:
    document_type: str
    name: str
    patterns: tuple[str, ...]
    confidence: float


class IraqiGovernmentDocumentDetector:
    """Classify Iraqi government documents using rules before optional LLM fallback."""

    DOCUMENT_TYPES = {
        "Cabinet Decision",
        "Law",
        "Regulation",
        "Cabinet Recommendation",
        "Ministerial Order",
        "Official Letter",
        "Circular",
        "Instruction",
        "Council Resolution",
        "Unknown",
    }

    def __init__(self, llm_classifier: LlmDocumentClassifier | None = None) -> None:
        self.llm_classifier = llm_classifier
        self.rules = (
            _Rule(
                "Cabinet Decision",
                "cabinet_decision_terms",
                (
                    "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
                    "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
                    "\u0642\u0631\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
                ),
                0.94,
            ),
            _Rule(
                "Cabinet Recommendation",
                "cabinet_recommendation_terms",
                (
                    "\u062a\u0648\u0635\u064a\u0629 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
                    "\u062a\u0648\u0635\u064a\u0629 \u0627\u0644\u0645\u062c\u0644\u0633",
                    "\u0627\u0642\u0631\u0627\u0631 \u062a\u0648\u0635\u064a\u0629",
                    "\u0625\u0642\u0631\u0627\u0631 \u062a\u0648\u0635\u064a\u0629",
                    "\u0627\u0644\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0627\u0631\u064a",
                ),
                0.88,
            ),
            _Rule(
                "Council Resolution",
                "council_resolution_terms",
                (
                    "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633",
                    "\u0642\u0631\u0631 \u0627\u0644\u0645\u062c\u0644\u0633",
                    "\u0645\u062c\u0644\u0633 \u0627\u0644\u0645\u062d\u0627\u0641\u0638\u0629",
                    "\u0645\u062c\u0644\u0633 \u0627\u0644\u0645\u062d\u0627\u0641\u0638\u064a\u0646",
                    "\u0645\u062c\u0644\u0633 \u0627\u0644\u0646\u0648\u0627\u0628",
                ),
                0.86,
            ),
            _Rule(
                "Law",
                "law_terms",
                (
                    "\u0642\u0627\u0646\u0648\u0646 \u0631\u0642\u0645",
                    "\u0628\u0627\u0633\u0645 \u0627\u0644\u0634\u0639\u0628",
                    "\u0631\u0626\u0627\u0633\u0629 \u0627\u0644\u062c\u0645\u0647\u0648\u0631\u064a\u0629",
                    "\u0635\u0648\u062a \u0645\u062c\u0644\u0633 \u0627\u0644\u0646\u0648\u0627\u0628",
                    "\u0627\u0633\u062a\u0646\u0627\u062f\u0627 \u0627\u0644\u0649 \u0627\u062d\u0643\u0627\u0645 \u0627\u0644\u0628\u0646\u062f",
                ),
                0.92,
            ),
            _Rule(
                "Regulation",
                "regulation_terms",
                (
                    "\u0646\u0638\u0627\u0645 \u0631\u0642\u0645",
                    "\u0646\u0638\u0627\u0645",
                    "\u0627\u0646\u0638\u0645\u0629",
                    "\u0627\u0644\u0646\u0638\u0627\u0645 \u0627\u0644\u062f\u0627\u062e\u0644\u064a",
                ),
                0.86,
            ),
            _Rule(
                "Instruction",
                "instruction_terms",
                (
                    "\u062a\u0639\u0644\u064a\u0645\u0627\u062a \u0631\u0642\u0645",
                    "\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
                    "\u0627\u0635\u062f\u0631\u0646\u0627 \u0627\u0644\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
                    "\u062a\u0646\u0641\u064a\u0630 \u0627\u0644\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
                ),
                0.84,
            ),
            _Rule(
                "Circular",
                "circular_terms",
                (
                    "\u0627\u0639\u0645\u0627\u0645",
                    "\u0627\u0639\u0645\u0627\u0645\u0646\u0627",
                    "\u064a\u0639\u0645\u0645",
                    "\u0627\u0644\u062a\u0639\u0645\u064a\u0645",
                    "\u0627\u0644\u0649 \u0643\u0627\u0641\u0629",
                ),
                0.84,
            ),
            _Rule(
                "Ministerial Order",
                "ministerial_order_terms",
                (
                    "\u0627\u0645\u0631 \u0648\u0632\u0627\u0631\u064a",
                    "\u0623\u0645\u0631 \u0648\u0632\u0627\u0631\u064a",
                    "\u0627\u0644\u0627\u0645\u0631 \u0627\u0644\u0648\u0632\u0627\u0631\u064a",
                    "\u0627\u0644\u0623\u0645\u0631 \u0627\u0644\u0648\u0632\u0627\u0631\u064a",
                    "\u0627\u0645\u0631 \u0627\u062f\u0627\u0631\u064a",
                    "\u0623\u0645\u0631 \u0625\u062f\u0627\u0631\u064a",
                ),
                0.90,
            ),
            _Rule(
                "Official Letter",
                "official_letter_terms",
                (
                    "\u0648\u0632\u0627\u0631\u0629",
                    "\u0643\u062a\u0627\u0628\u0646\u0627",
                    "\u0643\u062a\u0627\u0628\u0643\u0645",
                    "\u0625\u0644\u0649",
                    "\u0645\u0648\u0636\u0648\u0639",
                    "\u0645/\u0627",
                    "\u0627\u0644\u0639\u062f\u062f",
                    "\u0627\u0644\u062a\u0627\u0631\u064a\u062e",
                ),
                0.74,
            ),
        )

    def detect(self, document: CleanedDocument) -> DocumentTypeDetection:
        rule_detection = self._detect_with_rules(document)
        if rule_detection.confidence >= DOCUMENT_TYPE_CONFIDENCE_THRESHOLD:
            return rule_detection

        if self.llm_classifier is not None:
            llm_detection = self.llm_classifier.classify(document)
            if llm_detection.document_type in self.DOCUMENT_TYPES:
                return llm_detection

        return rule_detection

    def _detect_with_rules(self, document: CleanedDocument) -> DocumentTypeDetection:
        text = self._normalize(document.raw_text)
        best_type = "Unknown"
        best_confidence = 0.0
        matched_rules: list[str] = []

        for rule in self.rules:
            match_count = sum(1 for pattern in rule.patterns if self._normalize(pattern) in text)
            if not match_count:
                continue

            confidence = min(rule.confidence + ((match_count - 1) * 0.04), 0.98)
            if confidence > best_confidence:
                best_type = rule.document_type
                best_confidence = confidence
                matched_rules = [rule.name]
            elif rule.document_type == best_type:
                matched_rules.append(rule.name)

        return DocumentTypeDetection(
            document_type=best_type,
            confidence=round(best_confidence, 2),
            method="rule" if best_type != "Unknown" else "rule_unclassified",
            matched_rules=matched_rules,
        )

    def _normalize(self, text: str) -> str:
        normalized = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
        normalized = normalized.replace("\u0623", "\u0627")
        normalized = normalized.replace("\u0625", "\u0627")
        normalized = normalized.replace("\u0622", "\u0627")
        normalized = normalized.replace("\u0649", "\u064a")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized
