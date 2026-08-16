import json
import tempfile
import unittest
from pathlib import Path

from app.iraqi_government.detector import detect_document_type
from app.iraqi_government.extractor import extract_fixed_metadata, extract_legal_content
from app.iraqi_government.processor import process_document
from app.iraqi_government.validator import validate_standard_json


SAMPLE_LAW = """رئاسة الجمهورية

قانون مكافحة الفساد رقم (12) لسنة 2024

نشر في جريدة الوقائع العراقية بالعدد 4780 بتاريخ 1/2/2024

المادة 1
يهدف هذا القانون إلى تنظيم إجراءات مكافحة الفساد في مؤسسات الدولة.

المادة 2
تلتزم الجهات الحكومية بإصدار تعليمات تنفيذ هذا القانون.
"""


class IraqiGovernmentPreprocessorTests(unittest.TestCase):
    def test_detects_iraqi_legal_document_type(self):
        self.assertEqual(detect_document_type(SAMPLE_LAW), "law")
        self.assertEqual(detect_document_type("قرار مجلس الوزراء رقم 5 لسنة 2026"), "decision")

    def test_extracts_fixed_metadata(self):
        metadata = extract_fixed_metadata(SAMPLE_LAW, "sample.txt")

        self.assertEqual(metadata.document_type, "law")
        self.assertEqual(metadata.document_number, "12")
        self.assertEqual(metadata.year, "2024")
        self.assertEqual(metadata.issuing_authority, "رئاسة الجمهورية")
        self.assertEqual(metadata.gazette_name, "الوقائع العراقية")
        self.assertEqual(metadata.gazette_issue, "4780")

    def test_extracts_legal_content_articles(self):
        content = extract_legal_content(SAMPLE_LAW)

        self.assertIn("رئاسة الجمهورية", content.preamble)
        self.assertEqual(len(content.articles), 2)
        self.assertEqual(content.articles[0].number, "1")
        self.assertIn("مكافحة الفساد", content.articles[0].text)

    def test_processes_valid_document_and_saves_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "law.txt"
            output = Path(temp_dir) / "law.json"
            source.write_text(SAMPLE_LAW, encoding="utf-8")

            payload = process_document(source, output)

            self.assertTrue(payload["validation"]["valid"])
            self.assertTrue(output.exists())
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["metadata"]["document_type"], "law")
            self.assertTrue(saved["processing"]["rag_independent"])

    def test_validation_rejects_unknown_document_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "note.txt"
            source.write_text("ملاحظة عامة لا تحتوي على نوع قانوني واضح", encoding="utf-8")

            payload = process_document(source, require_valid=False)
            result = validate_standard_json(payload)

            self.assertFalse(result.valid)
            self.assertIn("document_type could not be detected", result.errors)


if __name__ == "__main__":
    unittest.main()
