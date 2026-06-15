"""Tests for safe document preparation and naming."""

import unittest
from unittest.mock import patch

from app.document_store import normalize_filename, prepare_document


class DocumentStoreTests(unittest.TestCase):
    def test_normalize_filename_adds_txt_extension(self):
        self.assertEqual(normalize_filename("new-law"), "new-law.txt")

    def test_normalize_filename_rejects_paths(self):
        with self.assertRaises(ValueError):
            normalize_filename("../outside.txt")

    @patch("app.document_store.create_embeddings")
    def test_prepare_document_adds_page_marker(self, mock_create_embeddings):
        mock_create_embeddings.return_value = [[0.1, 0.2]]

        filename, content, chunks, embeddings = prepare_document(
            "law",
            "Legal text",
        )

        self.assertEqual(filename, "law.txt")
        self.assertTrue(content.startswith("--- PAGE 1 ---"))
        self.assertEqual(chunks[0]["source_file"], "law.txt")
        self.assertEqual(embeddings, [[0.1, 0.2]])


if __name__ == "__main__":
    unittest.main()
