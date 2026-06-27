"""Tests for law/decision classification signal scoring."""

import unittest

from app.document_classifier import DECISION, LAW, classify_document


class DocumentClassifierTests(unittest.TestCase):
    def test_classifies_law_text(self):
        document_type, scores = classify_document(
            "قانون رقم 111 لسنة 1969\nالمادة 1\nينشر في الجريدة الرسمية"
        )

        self.assertEqual(document_type, LAW)
        self.assertGreater(scores["law_score"], scores["decision_score"])

    def test_classifies_decision_text(self):
        document_type, scores = classify_document(
            "قرار محكمة التمييز\nرقم الدعوى 12/2024\nقرر المحكمة رد الطعن"
        )

        self.assertEqual(document_type, DECISION)
        self.assertGreater(scores["decision_score"], scores["law_score"])


if __name__ == "__main__":
    unittest.main()
