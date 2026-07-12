"""Normalization tests for persistent uploaded legal documents."""

import unittest

from app.uploaded_documents import _normalized_document


class UploadedDocumentTests(unittest.TestCase):
    def test_normalizes_title_law_number_year_and_pages(self):
        document = _normalized_document(
            "abc123",
            "law.txt",
            [
                (1, "قانون حماية البيانات رقم 12 لسنة 2024"),
                (2, "المادة الأولى تسري أحكام هذا القانون."),
            ],
        )

        self.assertEqual(document["law_number"], "12")
        self.assertEqual(document["year"], "2024")
        self.assertEqual(document["articles"][1]["page_number"], 2)
        self.assertEqual(document["upload_id"], "abc123")
        self.assertTrue(document["source"].startswith("uploaded_abc123_"))

