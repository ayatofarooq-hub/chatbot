"""Tests for modular document loading and legal metadata extraction."""

import tempfile
import unittest
from pathlib import Path

from app.chunk_text import build_chunks_from_document
from app.document_loaders import (
    DocumentBlock,
    LoadedDocument,
    TxtDocumentLoader,
    detect_legal_references,
    supported_extensions,
)


class DocumentLoaderTests(unittest.TestCase):
    def test_registry_supports_docx_and_txt(self):
        self.assertEqual(supported_extensions(), (".docx", ".txt"))

    def test_detects_arabic_article_and_section_references(self):
        article, section = detect_legal_references("المادة (١٢) يعاقب...")
        self.assertEqual(article, "المادة (١٢)")
        self.assertEqual(section, "")

        article, section = detect_legal_references("الفصل الأول أحكام عامة")
        self.assertEqual(article, "")
        self.assertEqual(section, "الفصل الأول أحكام عامة")

    def test_txt_loader_preserves_page_markers_and_arabic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "law.txt"
            path.write_text(
                "--- PAGE 2 ---\nالمادة 5\nنص عربي قانوني",
                encoding="utf-8",
            )

            document = TxtDocumentLoader().load(path)

        self.assertEqual(document.blocks[0].page_number, 2)
        self.assertEqual(document.blocks[0].article_reference, "المادة 5")
        self.assertIn("نص عربي", document.blocks[0].text)

    def test_chunks_inherit_heading_and_article_metadata(self):
        document = LoadedDocument(
            source_file="law.docx",
            source_type="docx",
            title="قانون الاختبار",
            blocks=[
                DocumentBlock(
                    text="الفصل الأول",
                    block_type="heading",
                    heading_level=1,
                    section_reference="الفصل الأول",
                ),
                DocumentBlock(
                    text="المادة 7\nالنص القانوني",
                    article_reference="المادة 7",
                ),
            ],
            metadata={"author": "وزارة العدل"},
        )

        chunk = build_chunks_from_document(document)[0]

        self.assertEqual(chunk["source_file"], "law.docx")
        self.assertEqual(chunk["document_title"], "قانون الاختبار")
        self.assertEqual(chunk["section_title"], "الفصل الأول")
        self.assertEqual(chunk["legal_reference"], "المادة 7")
        self.assertEqual(chunk["document_author"], "وزارة العدل")


if __name__ == "__main__":
    unittest.main()
