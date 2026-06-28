"""Tests for mapping PostgreSQL law rows into retrieval documents."""

import unittest

from app.chunk_text import build_chunks_from_document
from app.postgres_laws import law_reference, row_to_document


class PostgresLawMappingTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": 42,
            "classification": "قانون",
            "law_number": "111",
            "law_year": 1969,
            "article_number": "405",
            "law_name": "قانون العقوبات",
            "summary": "نص موجز للمادة القانونية.",
        }

    def test_builds_complete_law_reference(self):
        self.assertEqual(
            law_reference(self.row),
            "قانون العقوبات رقم 111 لسنة 1969",
        )

    def test_maps_row_to_document_with_stable_provenance(self):
        document = row_to_document(self.row)

        self.assertEqual(document.source_file, "postgres_iraqi_laws_42")
        self.assertEqual(document.source_type, "postgresql")
        self.assertEqual(document.document_type, "قانون")
        self.assertEqual(document.blocks[0].article_reference, "المادة 405")
        self.assertEqual(document.metadata["database_id"], "42")

    def test_chunk_preserves_database_and_legal_metadata(self):
        chunk = build_chunks_from_document(row_to_document(self.row))[0]

        self.assertEqual(chunk["article_reference"], "المادة 405")
        self.assertEqual(chunk["legal_reference"], "المادة 405")
        self.assertEqual(chunk["document_database_id"], "42")
        self.assertEqual(
            chunk["document_law_reference"],
            "قانون العقوبات رقم 111 لسنة 1969",
        )


if __name__ == "__main__":
    unittest.main()
