"""Tests for modular document loading and legal metadata extraction."""

import tempfile
import unittest
from pathlib import Path

from app.chunk_text import build_chunks_from_document
from app.document_loaders import (
    DocumentBlock,
    LoadedDocument,
    PdfDocumentLoader,
    TxtDocumentLoader,
    detect_legal_references,
    supported_extensions,
)


class DocumentLoaderTests(unittest.TestCase):
    def test_registry_supports_pdf_docx_and_txt(self):
        self.assertEqual(supported_extensions(), (".docx", ".pdf", ".txt"))

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

    def test_pdf_loader_uses_text_layer_before_ocr(self):
        class FakePage:
            def extract_text(self):
                return "This text layer is long enough to skip OCR."

        text, used_ocr = PdfDocumentLoader()._extract_page_text(
            FakePage(),
            Path("law.pdf"),
            1,
        )

        self.assertIn("long enough", text)
        self.assertFalse(used_ocr)

    def test_pdf_loader_falls_back_to_ocr_for_empty_text_layer(self):
        class FakePage:
            def extract_text(self):
                return ""

        class FakeOcrLoader(PdfDocumentLoader):
            def _ocr_page(self, path, page_number):
                return "OCR text"

        text, used_ocr = FakeOcrLoader()._extract_page_text(
            FakePage(),
            Path("scan.pdf"),
            1,
        )

        self.assertEqual(text, "OCR text")
        self.assertTrue(used_ocr)

    def test_pdf_ocr_quality_prefers_arabic_legal_text(self):
        good = "قانون مجلس النواب وتشكيلاته رقم (١٣) لسنة ٢٠١٨"
        bad = "Ve tA Al gall random OCR noise"

        self.assertGreater(
            PdfDocumentLoader._ocr_quality_score(good),
            PdfDocumentLoader._ocr_quality_score(bad),
        )

    def test_chunks_inherit_heading_and_article_metadata(self):
        document = LoadedDocument(
            source_file="law.docx",
            source_type="docx",
            title="Ù‚Ø§Ù†ÙˆÙ† Ø§Ù„Ø§Ø®ØªØ¨Ø§Ø±",
            blocks=[
                DocumentBlock(
                    text="Ø§Ù„ÙØµÙ„ Ø§Ù„Ø£ÙˆÙ„",
                    block_type="heading",
                    heading_level=1,
                    section_reference="Ø§Ù„ÙØµÙ„ Ø§Ù„Ø£ÙˆÙ„",
                ),
                DocumentBlock(
                    text="Ø§Ù„Ù…Ø§Ø¯Ø© 7\nØ§Ù„Ù†Øµ Ø§Ù„Ù‚Ø§Ù†ÙˆÙ†ÙŠ",
                    article_reference="Ø§Ù„Ù…Ø§Ø¯Ø© 7",
                ),
            ],
            metadata={"author": "ÙˆØ²Ø§Ø±Ø© Ø§Ù„Ø¹Ø¯Ù„"},
        )

        chunk = build_chunks_from_document(document)[0]

        self.assertEqual(chunk["source_file"], "law.docx")
        self.assertEqual(chunk["document_title"], "Ù‚Ø§Ù†ÙˆÙ† Ø§Ù„Ø§Ø®ØªØ¨Ø§Ø±")
        self.assertEqual(chunk["section_title"], "Ø§Ù„ÙØµÙ„ Ø§Ù„Ø£ÙˆÙ„")
        self.assertEqual(chunk["legal_reference"], "Ø§Ù„Ù…Ø§Ø¯Ø© 7")
        self.assertEqual(chunk["document_author"], "ÙˆØ²Ø§Ø±Ø© Ø§Ù„Ø¹Ø¯Ù„")


if __name__ == "__main__":
    unittest.main()
