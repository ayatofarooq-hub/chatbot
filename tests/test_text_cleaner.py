"""Unit tests for legal text cleanup rules."""

import unittest

from app.extraction.text_cleaner import clean_text


class TextCleanerTests(unittest.TestCase):
    def test_removes_duplicate_spaces_and_empty_lines(self):
        raw = "This   is   a  line.\n\n\n  Another   line."
        cleaned = clean_text(raw)

        self.assertEqual(cleaned, "This is a line.\nAnother line.")

    def test_removes_page_numbers_and_broken_encoding(self):
        raw = "Header\n\nPage 1\n\nArticle 1.\nText with broken char \ufffd.\n\nPage 2\n\nArticle 2.\nMore text."
        cleaned = clean_text(raw)

        self.assertNotIn("Page 1", cleaned)
        self.assertNotIn("Page 2", cleaned)
        self.assertNotIn("\ufffd", cleaned)
        self.assertIn("Article 1.", cleaned)
        self.assertIn("Article 2.", cleaned)

    def test_removes_repeated_headers_and_footers(self):
        raw = (
            "Document Title\nHeader line\nPage 1\n\nContent A\nFooter line\n"
            "\fDocument Title\nHeader line\nPage 2\n\nContent B\nFooter line\n"
            "\fDocument Title\nHeader line\nPage 3\n\nContent C\nFooter line"
        )
        cleaned = clean_text(raw)

        self.assertNotIn("Document Title", cleaned)
        self.assertNotIn("Header line", cleaned)
        self.assertNotIn("Footer line", cleaned)
        self.assertIn("Content A", cleaned)
        self.assertIn("Content B", cleaned)
        self.assertIn("Content C", cleaned)

    def test_preserves_article_numbers_and_headings(self):
        raw = "ARTICLE 5\nSection 1.2\nHeading\n\nItem 1\nItem 2"
        cleaned = clean_text(raw)

        self.assertIn("ARTICLE 5", cleaned)
        self.assertIn("Section 1.2", cleaned)
        self.assertIn("Heading", cleaned)


if __name__ == "__main__":
    unittest.main()
