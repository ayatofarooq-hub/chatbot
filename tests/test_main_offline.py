"""Regression tests for the DOCX reading startup path."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from app import main as app_main
from app.chatbot import answer_with_qwen_3b
from app.chatbot import qwen_3b
from app.chunking import build_chunks_from_output_json
from app.build_index import chunk_metadata
from app.embeddings import create_chunk_embeddings
from app.extractors import (
    DocumentInfo,
    build_document_info_prompt,
    extract_regex_metadata_from_text,
    parse_document_info_response,
)
from app.json_builder import save_document_json
from app.rag_answer import AnswerResult
from app.schemas import DocumentModel
from app.utils import validate_document_json


class MainOfflineTests(unittest.TestCase):
    def test_main_writes_docx_json_without_crashing(self):
        with (
            patch.object(app_main, "create_data_directories") as create_data_directories,
            patch.object(app_main, "process_pipeline") as process_pipeline,
        ):
            app_main.main()

        create_data_directories.assert_called_once_with()
        process_pipeline.assert_called_once_with()

    def test_process_pipeline_marks_qwen_3b_chatbot_ready(self):
        with (
            patch.object(app_main, "write_docx_json_files"),
            patch.object(app_main, "index_output_json_files"),
            self.assertLogs(app_main.logger.name, level="INFO") as logs,
        ):
            app_main.process_pipeline()

        self.assertEqual([record.getMessage() for record in logs.records], ["Qwen 3B Chatbot: ready"])

    def test_print_docx_texts_prints_text_only(self):
        files = [
            app_main.INPUT_FOLDER / "contract.docx",
            app_main.INPUT_FOLDER / "judgment.docx",
        ]

        with (
            patch.object(app_main, "list_docx_files", return_value=files),
            patch.object(app_main, "read_docx_text", side_effect=["first\nsecond", "third"]),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                app_main.print_docx_texts()

        self.assertEqual(buffer.getvalue().splitlines(), ["first", "second", "third"])

    def test_read_docx_text_preserves_paragraph_order(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>First paragraph</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>paragraph</w:t></w:r></w:p>
    <w:p><w:r><w:t>Third paragraph</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            self.assertEqual(
                app_main.read_docx_text(docx_path),
                "First paragraph\nSecond\tparagraph\nThird paragraph",
            )

    def test_document_model_has_requested_fields_only(self):
        self.assertEqual(
            list(DocumentModel.__dataclass_fields__),
            ["source_file", "title", "paragraphs", "tables", "sections"],
        )

    def test_read_docx_document_builds_document_model(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Document Title</w:t></w:r></w:p>
    <w:p><w:r><w:t>Body paragraph</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>A1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B1</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            document = app_main.read_docx_document(docx_path)

        self.assertEqual(document.source_file, "sample.docx")
        self.assertEqual(document.title, "Document Title")
        self.assertEqual(
            [(paragraph.text, paragraph.type) for paragraph in document.paragraphs],
            [
                ("Document Title", "Paragraph"),
                ("Body paragraph", "Paragraph"),
                ("A1", "Paragraph"),
                ("B1", "Paragraph"),
            ],
        )
        self.assertEqual(document.tables, [[["A1", "B1"]]])
        self.assertEqual(document.sections, [])

    def test_classify_paragraph_detects_headings_only(self):
        self.assertEqual(app_main.classify_paragraph("باب الأحكام العامة"), "Heading")
        self.assertEqual(app_main.classify_paragraph("فصل التعاريف"), "Heading")
        self.assertEqual(app_main.classify_paragraph("مادة 1"), "Heading")
        self.assertEqual(app_main.classify_paragraph("هذا نص فقرة عادية"), "Paragraph")

    def test_extract_regex_metadata_from_text(self):
        text = "\n".join(
            [
                "قرار رقم 15 بتاريخ 12/5/2024",
                "قانون رقم 7 لسنة 2023",
                "المادة 3",
                "رقم المادة: 4",
            ]
        )

        metadata = extract_regex_metadata_from_text(text)

        self.assertEqual(metadata.decision_numbers, ["15"])
        self.assertEqual(metadata.law_numbers, ["7"])
        self.assertEqual(metadata.years, ["2023"])
        self.assertEqual(metadata.dates, ["12/5/2024"])
        self.assertEqual(metadata.article_numbers, ["3", "4"])

    def test_qwen_prompt_requests_document_info_only(self):
        prompt = build_document_info_prompt("نص الوثيقة هنا")

        self.assertIn('- "title": عنوان الوثيقة', prompt)
        self.assertIn('- "document_type": نوع الوثيقة', prompt)
        self.assertIn('- "summary": ملخص من سطرين', prompt)
        self.assertIn("- keywords", prompt)
        self.assertIn("- entities: وزارة، مجلس الوزراء، هيئة، محكمة فقط", prompt)
        self.assertIn('- "mentioned_laws": القوانين المذكورة', prompt)
        self.assertIn('- "mentioned_decisions": القرارات المذكورة', prompt)
        self.assertIn('- "constitution": الدستور', prompt)
        self.assertIn('- "legal_references": الإحالات القانونية', prompt)
        self.assertIn("نص الوثيقة هنا", prompt)
        self.assertNotIn("رقم القرار", prompt)
        self.assertNotIn("رقم القانون", prompt)
        self.assertNotIn("رقم المادة", prompt)
        self.assertNotIn("السنة", prompt)
        self.assertNotIn("التاريخ", prompt)

    def test_read_docx_document_info_uses_qwen_info_extractor(self):
        info = DocumentInfo(title="title", document_type="type", summary="summary")
        with (
            patch.object(app_main, "read_docx_text", return_value="document text"),
            patch.object(app_main, "extract_document_info_with_qwen", return_value=info) as extractor,
        ):
            result = app_main.read_docx_document_info(app_main.INPUT_FOLDER / "sample.docx")

        extractor.assert_called_once_with("document text")
        self.assertEqual(result, info)

    def test_build_document_json_contains_all_extraction_layers(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Document Title</w:t></w:r></w:p>
    <w:p><w:r><w:t>قرار رقم 15 بتاريخ 12/5/2024</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            qwen_info = DocumentInfo(
                title="Qwen Title",
                document_type="قرار",
                summary="سطر أول\nسطر ثان",
                keywords=["قانون"],
            )
            with patch.object(app_main, "extract_document_info_with_qwen", return_value=qwen_info):
                payload = app_main.build_docx_json(docx_path)

        self.assertEqual(payload["source_file"], "sample.docx")
        self.assertEqual(payload["title"], "Qwen Title")
        self.assertEqual(payload["document_type"], "قرار")
        self.assertEqual(payload["summary"], "سطر أول\nسطر ثان")
        self.assertEqual(payload["keywords"], ["قانون"])
        self.assertEqual(payload["paragraphs"][0]["text"], "Document Title")
        self.assertEqual(payload["regex_metadata"]["decision_numbers"], ["15"])

    def test_print_docx_json_prints_without_saving(self):
        with (
            patch.object(app_main, "list_docx_files", return_value=[app_main.INPUT_FOLDER / "sample.docx"]),
            patch.object(app_main, "build_docx_json", return_value={"title": "عنوان"}),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                app_main.print_docx_json()

        self.assertEqual(json.loads(buffer.getvalue()), {"title": "عنوان"})

    def test_write_docx_json_files_saves_to_output_folder(self):
        docx_file = app_main.INPUT_FOLDER / "sample.docx"

        with (
            patch.object(app_main, "list_docx_files", return_value=[docx_file]),
            patch.object(app_main, "build_docx_json", return_value={"title": "عنوان"}),
            patch.object(app_main, "save_document_json") as save_json,
        ):
            app_main.write_docx_json_files()

        save_json.assert_called_once_with(
            {"title": "عنوان"},
            app_main.OUTPUT_FOLDER / "sample.json",
        )

    def test_write_docx_json_files_logs_pipeline_steps(self):
        docx_file = app_main.INPUT_FOLDER / "sample.docx"

        with (
            patch.object(app_main, "list_unsupported_word_files", return_value=[]),
            patch.object(app_main, "list_docx_files", return_value=[docx_file]),
            patch.object(app_main, "build_docx_json", return_value={"title": "عنوان"}),
            patch.object(app_main, "save_document_json"),
            self.assertLogs(app_main.logger.name, level="INFO") as logs,
        ):
            app_main.write_docx_json_files()

        self.assertEqual(
            [record.getMessage() for record in logs.records],
            ["Start", "Batch: 1 files=1", "Save JSON: sample.json", "Finished"],
        )

    def test_write_docx_json_files_warns_about_doc_files(self):
        with (
            patch.object(app_main, "list_unsupported_word_files", return_value=[app_main.INPUT_FOLDER / "legacy.doc"]),
            patch.object(app_main, "list_docx_files", return_value=[]),
            self.assertLogs(app_main.logger.name, level="WARNING") as logs,
        ):
            app_main.write_docx_json_files()

        self.assertEqual(
            [record.getMessage() for record in logs.records],
            ["Warning: unsupported Word format .doc: legacy.doc"],
        )

    def test_batch_docx_files_supports_100_200_300(self):
        files = [Path(f"file-{index}.docx") for index in range(250)]

        self.assertEqual([len(batch) for batch in app_main.batch_docx_files(files, 100)], [100, 100, 50])
        self.assertEqual([len(batch) for batch in app_main.batch_docx_files(files, 200)], [200, 50])
        self.assertEqual([len(batch) for batch in app_main.batch_docx_files(files, 300)], [250])

    def test_batch_docx_files_rejects_unsupported_batch_size(self):
        with self.assertRaisesRegex(ValueError, "Unsupported batch size"):
            app_main.batch_docx_files([Path("sample.docx")], 50)

    def test_build_chunks_from_output_json_uses_saved_payload(self):
        payload = {
            "source_file": "sample.docx",
            "title": "Document Title",
            "document_type": "قرار",
            "summary": "summary",
            "legal_references": ["المادة 1"],
            "paragraphs": [
                {"text": "Document Title", "type": "Paragraph"},
                {"text": "Body paragraph", "type": "Paragraph"},
            ],
            "regex_metadata": {
                "law_numbers": ["7"],
                "years": ["2023"],
                "article_numbers": ["1"],
            },
        }

        chunks = build_chunks_from_output_json(payload)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["source_file"], "sample.docx")
        self.assertEqual(chunks[0]["document_type"], "قرار")
        self.assertEqual(chunks[0]["document_title"], "Document Title")
        self.assertEqual(chunks[0]["article_reference"], "1")
        self.assertEqual(chunks[0]["document_law_number"], "7")
        self.assertEqual(chunks[0]["document_law_year"], "2023")
        self.assertIn("Body paragraph", chunks[0]["text"])

    def test_index_output_json_files_skips_when_no_json_files(self):
        with (
            patch.object(app_main, "list_output_json_files", return_value=[]),
            self.assertLogs(app_main.logger.name, level="INFO") as logs,
        ):
            chunk_count = app_main.index_output_json_files()

        self.assertEqual(chunk_count, 0)
        self.assertEqual([record.getMessage() for record in logs.records], ["ChromaDB: no JSON files"])

    def test_index_output_json_files_updates_chromadb_and_citation_registry(self):
        chunks = [{"id": "chunk-1", "source_file": "sample.docx", "text": "text", "page_number": 1, "chunk_index": 0}]
        fake_client = object()
        fake_collection = object()

        with (
            patch.object(app_main, "list_output_json_files", return_value=[Path("sample.json")]),
            patch.object(app_main, "load_output_chunks", return_value=chunks),
            patch.object(app_main, "create_chunk_embeddings", return_value=[[0.1, 0.2]]) as create_embeddings,
            patch("app.build_index.reset_collection", return_value=fake_collection) as reset_collection,
            patch("app.build_index.add_chunks") as add_chunks,
            patch("app.citation_registry.save_registry") as save_registry,
            patch("chromadb.PersistentClient", return_value=fake_client),
        ):
            chunk_count = app_main.index_output_json_files()

        self.assertEqual(chunk_count, 1)
        create_embeddings.assert_called_once_with(chunks)
        reset_collection.assert_called_once_with(fake_client)
        add_chunks.assert_called_once_with(fake_collection, chunks, [[0.1, 0.2]])
        save_registry.assert_called_once_with(chunks)

    def test_chroma_metadata_excludes_complete_source_text_fields(self):
        metadata = chunk_metadata(
            {
                "id": "chunk-1",
                "source_file": "decision.docx",
                "document_id": "legal_json_doc",
                "text": "retrieval chunk",
                "embedding_text": "embedding text",
                "long_text": "complete long text must stay in original json",
                "body": "complete body fallback",
                "original_long_text": "complete original long text",
                "original_json_path": "legal_document_parser/output/json/decision.json",
                "has_full_source_text": True,
            }
        )

        self.assertEqual(metadata["chunk_id"], "chunk-1")
        self.assertEqual(metadata["document_id"], "legal_json_doc")
        self.assertEqual(metadata["original_json_path"], "legal_document_parser/output/json/decision.json")
        self.assertTrue(metadata["has_full_source_text"])
        self.assertNotIn("long_text", metadata)
        self.assertNotIn("body", metadata)
        self.assertNotIn("original_long_text", metadata)

    def test_create_chunk_embeddings_delegates_to_existing_embedding_builder(self):
        chunks = [{"text": "text"}]

        with patch("app.build_index.create_embeddings", return_value=[[0.3, 0.4]]) as create_embeddings:
            embeddings = create_chunk_embeddings(chunks)

        create_embeddings.assert_called_once_with(chunks)
        self.assertEqual(embeddings, [[0.3, 0.4]])

    def test_answer_with_qwen_3b_uses_search_registry_and_chatbot(self):
        search_results = {"documents": [["chunk"]], "metadatas": [[{"chunk_id": "1"}]]}
        validated_results = {"documents": [["valid chunk"]], "metadatas": [[{"chunk_id": "1"}]]}
        registry = {"by_chunk_id": {"1": {"chunk_id": "1"}}}

        with (
            patch.object(qwen_3b, "get_quick_response", return_value=None),
            patch.object(qwen_3b, "search", return_value=search_results) as search,
            patch.object(qwen_3b, "load_registry", return_value=registry) as load_registry,
            patch.object(
                qwen_3b,
                "filter_results_to_registered",
                return_value=(validated_results, ["registry warning"]),
            ) as filter_results,
            patch.object(
                qwen_3b,
                "generate_answer",
                return_value=AnswerResult(content="answer", warnings=["answer warning"]),
            ) as generate_answer,
        ):
            result = answer_with_qwen_3b("question")

        search.assert_called_once_with("question")
        load_registry.assert_called_once_with()
        filter_results.assert_called_once_with(search_results, registry=registry)
        generate_answer.assert_called_once_with("question", validated_results)
        self.assertEqual(result.content, "answer")
        self.assertEqual(result.warnings, ["registry warning", "answer warning"])

    def test_answer_with_qwen_3b_returns_quick_response_without_search(self):
        with (
            patch.object(qwen_3b, "get_quick_response", return_value="quick"),
            patch.object(qwen_3b, "search") as search,
        ):
            result = answer_with_qwen_3b("مرحبا")

        search.assert_not_called()
        self.assertEqual(result, AnswerResult(content="quick", warnings=[]))

    def test_answer_with_qwen_3b_falls_back_to_context_when_model_is_insufficient(self):
        validated_results = {
            "documents": [["قــرّر مجلس الوزراء\nأولًا : الموافقة على استثناء عقد تصليح عام شامل للطائرات المروحية."]],
            "metadatas": [[{"chunk_id": "1", "source_file": "decision.docx", "page_number": 1}]],
        }
        registry = {
            "by_chunk_id": {
                "1": {
                    "chunk_id": "1",
                    "law": "قرار مجلس الوزراء",
                    "article": "",
                    "law_name": "قرار مجلس الوزراء",
                    "source_file": "decision.docx",
                    "page_number": 1,
                }
            }
        }

        with (
            patch.object(qwen_3b, "get_quick_response", return_value=None),
            patch.object(qwen_3b, "search", return_value=validated_results),
            patch.object(qwen_3b, "load_registry", return_value=registry),
            patch.object(qwen_3b, "filter_results_to_registered", return_value=(validated_results, [])),
            patch.object(
                qwen_3b,
                "generate_answer",
                return_value=AnswerResult(
                    content="لم يحتوي المصادر القانونية المسترجعة على إجابة واضحة لهذا السؤال.",
                    warnings=[],
                ),
            ),
        ):
            result = answer_with_qwen_3b("ماذا قرر مجلس الوزراء؟")

        self.assertIn("الموافقة على استثناء عقد تصليح", result.content)

    def test_index_output_json_files_logs_chunking_before_chromadb(self):
        chunks = [{"id": "chunk-1", "source_file": "sample.docx", "text": "text", "page_number": 1, "chunk_index": 0}]

        with (
            patch.object(app_main, "list_output_json_files", return_value=[Path("sample.json")]),
            patch.object(app_main, "load_output_chunks", return_value=chunks),
            patch.object(app_main, "create_chunk_embeddings", return_value=[[0.1, 0.2]]),
            patch("app.build_index.reset_collection", return_value=object()),
            patch("app.build_index.add_chunks"),
            patch("app.citation_registry.save_registry"),
            patch("chromadb.PersistentClient", return_value=object()),
            self.assertLogs(app_main.logger.name, level="INFO") as logs,
        ):
            app_main.index_output_json_files()

        self.assertEqual(
            [record.getMessage() for record in logs.records],
            [
                "Chunking: 1 files",
                "Embedding: 1 chunks",
                "ChromaDB: 1 chunks",
                "citation_registry.json",
            ],
        )

    def test_build_docx_json_logs_read_extract_and_llm_steps(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Document Title</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            qwen_info = DocumentInfo(
                title="Document Title",
                document_type="قرار",
                summary="سطر أول\nسطر ثان",
            )
            with (
                patch.object(app_main, "extract_document_info_with_qwen", return_value=qwen_info),
                self.assertLogs(app_main.logger.name, level="INFO") as logs,
            ):
                app_main.build_docx_json(docx_path)

        self.assertEqual(
            [record.getMessage() for record in logs.records],
            ["Read File: sample.docx", "Extract: sample.docx", "LLM: sample.docx"],
        )

    def test_save_document_json_writes_utf8_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "sample.json"
            save_document_json({"title": "عنوان"}, output_file)

            payload = json.loads(output_file.read_text(encoding="utf-8"))

        self.assertEqual(payload, {"title": "عنوان"})

    def test_parse_document_info_response_reads_required_fields(self):
        content = json.dumps(
            {
                "title": "عنوان",
                "document_type": "قرار",
                "summary": "سطر أول\nسطر ثان",
                "keywords": ["تعليمات", "قانون"],
            },
            ensure_ascii=False,
        )

        info = parse_document_info_response(content)

        self.assertEqual(info.title, "عنوان")
        self.assertEqual(info.document_type, "قرار")
        self.assertEqual(info.summary, "سطر أول\nسطر ثان")
        self.assertEqual(info.keywords, ["تعليمات", "قانون"])

    def test_validate_document_json_warns_about_missing_required_fields(self):
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            missing_fields = validate_document_json(
                {"title": "عنوان", "summary": "", "document_type": ""}
            )

        self.assertEqual(missing_fields, ["summary", "document_type"])
        self.assertIn(
            "Warning: missing required fields: summary, document_type",
            buffer.getvalue(),
        )

    def test_build_docx_json_warns_but_returns_payload_when_required_fields_missing(self):
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Fallback Title</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "sample.docx"
            with ZipFile(docx_path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            buffer = io.StringIO()
            with (
                patch.object(app_main, "extract_document_info_with_qwen", return_value=DocumentInfo()),
                redirect_stdout(buffer),
            ):
                payload = app_main.build_docx_json(docx_path)

        self.assertEqual(payload["title"], "Fallback Title")
        self.assertEqual(payload["summary"], "")
        self.assertEqual(payload["document_type"], "")
        self.assertIn("Warning: missing required fields", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
