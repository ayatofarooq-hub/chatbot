"""Normalization tests for persistent uploaded legal documents."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.uploaded_documents import _normalized_document, delete_uploaded_document
from backend.services.json_repository import JsonRepository


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

    def test_delete_promotes_upload_to_source_corpus(self):
        with TemporaryDirectory() as temporary_directory:
            repository = JsonRepository(Path(temporary_directory))
            repository.append_document(
                {
                    "id": "upload_abc123",
                    "upload_id": "abc123",
                    "original_filename": "law.pdf",
                    "uploaded_at": "2026-07-22T00:00:00+00:00",
                    "source": "uploaded_abc123_law.pdf",
                    "title": "law",
                    "articles": [{"text": "legal text"}],
                }
            )

            with patch(
                "app.uploaded_documents.JsonRepository",
                return_value=repository,
            ):
                delete_uploaded_document("abc123")

            promoted = repository.find_by_id("upload_abc123")

        self.assertIsNotNone(promoted)
        self.assertNotIn("upload_id", promoted)
        self.assertEqual(promoted["source_origin"], "uploaded")
        self.assertEqual(promoted["source"], "uploaded_abc123_law.pdf")
