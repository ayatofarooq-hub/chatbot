"""Tests for citation-vetting behavior shared by CLI and Streamlit."""

import unittest
from unittest.mock import patch

import httpx

from app.legal_lookup import answer_exact_law
from app.prompts import INSUFFICIENT_CONTEXT_MESSAGE
from app.rag_answer import (
    AnswerResult,
    MISSING_DECISION_NUMBER_ANSWER,
    NO_USABLE_LEGAL_SOURCE_TEXT,
    build_context,
    complete_uploaded_source_answer,
    ensure_answer_citations,
    exact_law_sources,
    generate_answer,
    get_quick_response,
    detailed_decision_answer_from_context,
    is_legal_title_only,
    meaningful_answer_from_context,
    missing_required_query_markers,
    product_price_answer_from_context,
    repair_empty_or_title_answer,
    decision_number_answer,
    document_date_answer,
    source_book_answer,
    results_with_full_document_context,
    wants_full_document_context,
    _retrieved_documents_for_source,
)
from app.ui import answer_question


RESULTS = {
    "documents": [["retrieved legal text"]],
    "metadatas": [[{"chunk_id": "chunk-1", "source_file": "law.pdf", "page_number": 1}]],
    "distances": [[0.1]],
}

REGISTRY = {
    "by_chunk_id": {
        "chunk-1": {
            "law_number": "1",
            "law_year": "2020",
            "article_number": "2",
            "law_name": "Test Law",
            "classification": "civil",
        }
    }
}

SECTION_HEADING = (
    "\u062a\u0641\u0643\u064a\u0643 \u0627\u0644\u0642\u0648\u0627\u0646\u064a\u0646 "
    "\u0645\u0646 (\u0661\u0661) \u0625\u0644\u0649 (\u0662\u0660) - "
    "\u0627\u0644\u062a\u0634\u0631\u064a\u0639\u0627\u062a "
    "\u0627\u0644\u0642\u0636\u0627\u0626\u064a\u0629 "
    "\u0648\u0627\u0644\u0623\u0645\u0646\u064a\u0629 "
    "\u0648\u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631\u064a\u0629"
)


class AnswerFlowTests(unittest.TestCase):
    def test_build_context_uses_structured_document_full_source_text(self):
        results = {
            "documents": [["relevant chunk"]],
            "metadatas": [
                [
                    {
                        "chunk_id": "chunk-1",
                        "source_file": "decision.docx",
                        "title": "قــرار مجلــس الــوزراء",
                        "document_type": "قرار مجلس الوزراء",
                        "year": "2024",
                        "issue_date": "30/10/2024",
                        "session_number": "الرابعة والاربعين",
                        "session_date": "29/10/2024",
                        "document_reference_numbers": "و/623 | 15/8/2024",
                        "recommendation_numbers": "24315 ق",
                        "entities": "وزارة النفط | المجلس الوزاري للاقتصاد",
                    }
                ]
            ],
        }
        with patch("app.rag_answer.load_registry", return_value={"by_chunk_id": {}}), patch(
            "app.rag_answer._source_text_for_source_file",
            return_value="FULL LONG TEXT",
        ):
            context = build_context(results)

        self.assertIn("DOCUMENT 1", context)
        self.assertIn("Title:\nقــرار مجلــس الــوزراء", context)
        self.assertIn("References:\nو/623\n15/8/2024\n24315 ق", context)
        self.assertIn("Entities:\nوزارة النفط\nالمجلس الوزاري للاقتصاد", context)
        self.assertIn("FULL SOURCE TEXT:\nFULL LONG TEXT", context)
        self.assertNotIn("MULTI-DOCUMENT SOURCE RULE", context)

    def test_build_context_adds_source_rule_for_multiple_documents(self):
        results = {
            "documents": [["first text", "second text"]],
            "metadatas": [[
                {"chunk_id": "chunk-1", "source_file": "first.docx", "document_id": "doc-1"},
                {"chunk_id": "chunk-2", "source_file": "second.docx", "document_id": "doc-2"},
            ]],
            "relevance_scores": [[0.9, 0.7]],
        }
        with patch("app.rag_answer.load_registry", return_value={"by_chunk_id": {}}), patch(
            "app.rag_answer._source_text_for_source_file",
            side_effect=lambda source: f"FULL {source}",
        ):
            context = build_context(results)

        self.assertIn("MULTI-DOCUMENT SOURCE RULE", context)
        self.assertIn("DOCUMENT 1", context)
        self.assertIn("DOCUMENT 2", context)
        self.assertIn("Relevance Score:\n0.9", context)
        self.assertIn("Relevance Score:\n0.7", context)

    def test_product_price_answer_extracts_fuel_oil_price_change(self):
        results = {
            "documents": [[
                "منتوج زيت الوقود (150.000) دينار / م3 بدلًا من (350.000) دينار / م3 ."
            ]],
            "metadatas": [[
                {
                    "document_id": "legal_json_60df7b9e0c09",
                    "source_file": "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx",
                    "document_type": "قرار مجلس الوزراء",
                    "year": "2024",
                    "issue_date": "30/10/2024",
                }
            ]],
        }

        self.assertEqual(
            product_price_answer_from_context("كم أصبح سعر منتوج زيت الوقود؟", results),
            "تم تعديل سعر منتوج زيت الوقود ليصبح 150.000 دينار / م3 بدلًا من 350.000 دينار / م3.",
        )

    def test_product_price_answer_extracts_diesel_from_about_question(self):
        results = {
            "documents": [[
                "منتوج زيت الغاز (400) دينار / لتر بدلًا من (750) دينار / لتر ."
            ]],
            "metadatas": [[{"source_file": "decision.docx"}]],
        }

        self.assertEqual(
            product_price_answer_from_context("ما الذي قرره مجلس الوزراء بشأن زيت الغاز؟", results),
            "تم تعديل سعر منتوج زيت الغاز ليصبح 400 دينار / لتر بدلًا من 750 دينار / لتر.",
        )

    def test_document_date_answer_distinguishes_issue_and_session_dates(self):
        results = {
            "documents": [["قرار مجلس الوزراء"]],
            "metadatas": [[
                {
                    "issue_date": "30/10/2024",
                    "session_date": "29/10/2024",
                }
            ]],
        }

        issue_answer = document_date_answer("متى صدر القرار؟", results)
        session_answer = document_date_answer("متى عقدت الجلسة؟", results)

        self.assertIsNotNone(issue_answer)
        self.assertEqual(issue_answer.content, "تاريخ صدور القرار: 30/10/2024.")
        self.assertIsNotNone(session_answer)
        self.assertEqual(session_answer.content, "تاريخ انعقاد الجلسة: 29/10/2024.")

    def test_source_book_answer_uses_full_source_text(self):
        results = {
            "documents": [["منتوج زيت الغاز (400) دينار / لتر بدلًا من (750) دينار / لتر ."]],
            "metadatas": [[{"source_file": "fuel-decision.docx"}]],
        }
        full_text = (
            "الموافقة على تعديل أسعار المنتجات النفطية المجهزة إلى شركة ناقلات النفط العراقية\n"
            "الواردة بكتاب وزارة النفط المرقم بالعدد ( و/623 ) المؤرخ في 15/8/2024 لتصبح كالآتي :"
        )

        with patch("app.rag_answer._source_text_for_source_file", return_value=full_text):
            answer = source_book_answer("بناءً على أي كتاب تم تعديل الأسعار؟", results)

        self.assertIsNotNone(answer)
        self.assertEqual(
            answer.content,
            "كتاب وزارة النفط المرقم بالعدد (و/623) المؤرخ في 15/8/2024.",
        )

    @patch("app.rag_answer.call_chat_model")
    @patch("app.rag_answer.load_registry")
    @patch("app.rag_answer.filter_results_to_registered")
    def test_generate_answer_returns_clear_error_when_json_has_no_usable_source_text(
        self,
        mock_filter_results,
        mock_load_registry,
        mock_call_chat_model,
    ):
        results = {
            "documents": [["SHORT CHUNK THAT MUST NOT BE SENT TO LLM"]],
            "metadatas": [[
                {
                    "chunk_id": "empty-json",
                    "source_file": "empty.json",
                    "source_type": "legal_document_parser_json",
                    "json_path": "legal_document_parser/output/json/empty.json",
                    "has_full_document": True,
                }
            ]],
            "distances": [[0.1]],
        }
        mock_load_registry.return_value = {"by_chunk_id": {"empty-json": {"chunk_id": "empty-json"}}}
        mock_filter_results.return_value = (results, [])

        result = generate_answer("ما مضمون القرار؟", results)

        self.assertEqual(result.content, NO_USABLE_LEGAL_SOURCE_TEXT)
        self.assertIn(NO_USABLE_LEGAL_SOURCE_TEXT, result.warnings)
        mock_call_chat_model.assert_not_called()

    def test_required_query_markers_ignore_tatweel_inside_arabic_words(self):
        question = "ماذا قرر مجلس الوزراء في الجلسة الثالثة والخمسين المنعقدة في 30/12/2024؟"
        context = "قــرّر مجلــس الــوزراء في جلستــه الاعتياديــة الثالثة والخمسيـن المنعقــدة في 30/12/2024"

        self.assertEqual(missing_required_query_markers(question, context), [])

    def test_detailed_decision_answer_keeps_decision_body(self):
        context = "\n".join(
            [
                "قـــــرار",
                "قــرّر مجلس الوزراء",
                "أولًا : الموافقة على استثناء عقد تصليح عام شامل.",
                "ثانيًا : تخويل وزارة الدفاع صلاحية التنفيذ.",
                "الأمين العام لمجلس الوزراء",
            ]
        )

        answer = detailed_decision_answer_from_context(context)

        self.assertIn("أولًا : الموافقة", answer)
        self.assertIn("ثانيًا : تخويل", answer)
        self.assertNotIn("الأمين العام", answer)

    def test_exact_law_lookup_returns_full_requested_section_only(self):
        question = (
            "١٤. قانون الأسلحة رقم "
            "(٥١) لسنة ٢٠١٧"
        )

        result = answer_exact_law(question)

        self.assertIsNotNone(result)
        answer = result["answer"]
        self.assertIn("قانون الأسلحة", answer)
        self.assertIn("الأسباب الموجبة", answer)
        self.assertIn("المادة (٢٧)", answer)
        self.assertNotIn("قانون مجلس القضاء الأعلى", answer)

    def test_exact_law_lookup_includes_group_source(self):
        result = answer_exact_law("قانون هيئة الحشد الشعبي رقم (٤٠) لسنة ٢٠١٦")

        self.assertIsNotNone(result)
        expected_source = (
            "تفكيك القوانين من (١١) إلى (٢٠) - "
            "التشريعات القضائية والأمنية والاستثمارية"
        )
        self.assertTrue(result["answer"].endswith(f"المصدر: {expected_source}"))
        self.assertEqual(result["citations"][0]["source_file"], expected_source)
        self.assertIn("قانون هيئة الحشد الشعبي", result["answer"])
        self.assertNotIn("قانون الأسلحة رقم", result["answer"])

    def test_exact_law_lookup_prefers_detailed_uploaded_law_section(self):
        result = answer_exact_law("قانون حماية الأطباء رقم (١١) لسنة ٢٠١٣")

        self.assertIsNotNone(result)
        answer = result["answer"]
        self.assertIn("الأسباب الموجبة", answer)
        self.assertIn("الهيكل التنظيمي", answer)
        self.assertIn("المادة (١)", answer)
        self.assertIn("المادة (٣)", answer)
        self.assertIn("المادة (٥)", answer)
        self.assertIn("المادة (٦) - تجريم السنن العشائرية", answer)
        self.assertNotIn("قانون هيئة الحشد الشعبي رقم", answer)
        self.assertEqual(answer.count("تفكيك القوانين من"), 1)
        self.assertTrue(
            answer.endswith(
                "المصدر: تفكيك القوانين من (١١) إلى (٢٠) - "
                "التشريعات القضائية والأمنية والاستثمارية"
            )
        )

    def test_exact_law_lookup_keeps_answer_limited_to_requested_law(self):
        result = answer_exact_law("قانون هيئة الحشد الشعبي رقم (٤٠) لسنة ٢٠١٦")

        self.assertIsNotNone(result)
        answer = result["answer"]
        self.assertIn("المادة (١) - الفقرة ١", answer)
        self.assertIn("المادة (١) - الفقرة ٢", answer)
        self.assertIn("المادة (١) - الفقرة ٣", answer)
        self.assertIn("المادة (٢)", answer)
        self.assertNotIn("نصوص ذات صلة بهذا القانون", answer)
        self.assertNotIn("إقرار الهيكل القانوني الثابت لهيئة الحشد الشعبي", answer)
        self.assertNotIn("قانون الأسلحة رقم", answer)
        self.assertNotIn("قانون مكافحة الجرائم المعلوماتية", answer)
        self.assertNotIn("قانون الاستثمار العراقي", answer)
        self.assertNotIn("قانون مكافحة الأمية", answer)

    def test_incomplete_question_returns_without_calling_model(self):
        self.assertIn("سؤال قانوني مكتمل", get_quick_response("ص"))

    @patch("app.rag_answer.validate_answer")
    @patch("app.rag_answer.call_chat_model")
    @patch("app.rag_answer.load_registry")
    @patch("app.rag_answer.filter_results_to_registered")
    def test_generate_answer_keeps_first_answer_when_correction_times_out(
        self,
        mock_filter_results,
        mock_load_registry,
        mock_call_chat_model,
        mock_validate_answer,
    ):
        mock_load_registry.return_value = REGISTRY
        mock_filter_results.return_value = (RESULTS, [])
        mock_call_chat_model.side_effect = [
            "first answer",
            httpx.ReadTimeout("correction timed out"),
        ]
        mock_validate_answer.return_value = ["citation warning"]

        result = generate_answer("question", RESULTS)

        self.assertIn("Analysis / Relevant Legal Sources", result.content)
        self.assertIn("Test Law", result.content)
        self.assertIn("Answer\n\nfirst answer", result.content)
        self.assertNotIn("✅", result.content)
        self.assertIn("citation warning", result.warnings)
        self.assertTrue(
            any("تم عرض الإجابة الأولية" in warning for warning in result.warnings)
        )

    @patch("app.rag_answer.validate_answer")
    @patch("app.rag_answer.call_chat_model")
    @patch("app.rag_answer.load_registry")
    @patch("app.rag_answer.filter_results_to_registered")
    def test_generate_answer_returns_failed_vetting_as_warnings(
        self,
        mock_filter_results,
        mock_load_registry,
        mock_call_chat_model,
        mock_validate_answer,
    ):
        mock_load_registry.return_value = REGISTRY
        mock_filter_results.return_value = (RESULTS, [])
        mock_call_chat_model.side_effect = ["first answer", "corrected answer"]
        mock_validate_answer.side_effect = [["needs correction"], ["needs correction"]]

        result = generate_answer("question", RESULTS)

        self.assertIn("Analysis / Relevant Legal Sources", result.content)
        self.assertIn("Answer\n\ncorrected answer", result.content)
        self.assertEqual(result.warnings, ["needs correction"])
        self.assertEqual(mock_call_chat_model.call_count, 2)

    @patch("app.rag_answer.load_registry", return_value=REGISTRY)
    def test_ensure_answer_citations_adds_structured_sources(self, _mock_registry):
        answer = ensure_answer_citations("short answer", RESULTS)

        self.assertIn("Analysis / Relevant Legal Sources\n\nTest Law", answer)
        self.assertIn("Answer\n\nshort answer", answer)
        self.assertNotIn("📌", answer)

    def test_exact_law_sources_prefers_embedded_section_heading(self):
        results = {
            "documents": [[
                "Other law\n\n"
                f"{SECTION_HEADING}\n"
                "\u0661\u0661. \u0642\u0627\u0646\u0648\u0646 "
                "\u0627\u0644\u0639\u0641\u0648 \u0627\u0644\u0639\u0627\u0645"
            ]],
            "metadatas": [[{"chunk_id": "chunk-1"}]],
        }

        self.assertEqual(exact_law_sources(results, registry=REGISTRY), [SECTION_HEADING])

    def test_exact_law_sources_infers_group_from_law_item_number(self):
        results = {
            "documents": [[
                "\u062a\u0641\u0643\u064a\u0643 \u0627\u0644\u0642\u0648\u0627\u0646\u064a\u0646 "
                "\u0645\u0646 (\u0661) \u0625\u0644\u0649 (\u0661\u0660) - "
                "\u0627\u0644\u0645\u0628\u0627\u062f\u0626 "
                "\u0627\u0644\u062f\u0633\u062a\u0648\u0631\u064a\u0629 "
                "\u0648\u0627\u0644\u062c\u0646\u0627\u0626\u064a\u0629\n"
                "\u0661\u0662. \u0642\u0627\u0646\u0648\u0646 "
                "\u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0623\u0637\u0628\u0627\u0621 "
                "\u0631\u0642\u0645 (\u0661\u0661) \u0644\u0633\u0646\u0629 \u0662\u0660\u0661\u0663"
            ]],
            "metadatas": [[{"chunk_id": "chunk-1"}]],
        }

        self.assertEqual(exact_law_sources(results, registry=REGISTRY), [SECTION_HEADING])

    def test_exact_law_sources_prefers_uploaded_filename_for_generic_title(self):
        registry = {
            "by_chunk_id": {
                "uploaded-chunk": {
                    "law_name": "\u062f\u0627\u0626\u0631\u0629 \u0634\u0624\u0648\u0646 \u0645\u062c\u0644\u0633 \u0627\u0644",
                    "legal_reference": "\u062f\u0627\u0626\u0631\u0629 \u0634\u0624\u0648\u0646 \u0645\u062c\u0644\u0633 \u0627\u0644",
                    "source_file": (
                        "uploaded_5c4f3860af286bd6_"
                        "\u0642\u0631\u0627\u0631_\u0627\u0642\u0631\u0627\u0631_"
                        "\u0627\u0644\u0636\u0645\u0627\u0646\u0629_"
                        "\u0627\u0644\u0633\u064a\u0627\u062f\u064a\u0629_"
                        "\u0645\u0635\u0646\u0639_\u0627\u0644\u0632\u062c\u0627\u062c.pdf"
                    ),
                }
            }
        }
        results = {
            "documents": [["\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 \u0631\u0642\u0645 24858"]],
            "metadatas": [[
                {
                    "chunk_id": "uploaded-chunk",
                    "source_file": (
                        "uploaded_5c4f3860af286bd6_"
                        "\u0642\u0631\u0627\u0631_\u0627\u0642\u0631\u0627\u0631_"
                        "\u0627\u0644\u0636\u0645\u0627\u0646\u0629_"
                        "\u0627\u0644\u0633\u064a\u0627\u062f\u064a\u0629_"
                        "\u0645\u0635\u0646\u0639_\u0627\u0644\u0632\u062c\u0627\u062c.pdf"
                    ),
                    "document_upload_id": "5c4f3860af286bd6",
                    "document_title": "\u062f\u0627\u0626\u0631\u0629 \u0634\u0624\u0648\u0646 \u0645\u062c\u0644\u0633 \u0627\u0644",
                }
            ]],
        }

        self.assertEqual(
            exact_law_sources(results, registry=registry),
            ["\u0642\u0631\u0627\u0631 \u0627\u0642\u0631\u0627\u0631 \u0627\u0644\u0636\u0645\u0627\u0646\u0629 \u0627\u0644\u0633\u064a\u0627\u062f\u064a\u0629 \u0645\u0635\u0646\u0639 \u0627\u0644\u0632\u062c\u0627\u062c.pdf"],
        )

    def test_short_uploaded_decision_answer_is_replaced_with_full_source_text(self):
        source_text = (
            "\u0642\u0640\u0640\u0640\u0640\u0640\u0631\u0627\u0631\n"
            "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621\n"
            "\u0631\u0642\u0645 (99999) \u0644\u0633\u0646\u0629 2024\n"
            "\u0628\u0646\u0627\u0621\u064b \u0639\u0644\u0649 \u0645\u0627 "
            "\u0639\u0631\u0636\u062a\u0647 \u0648\u0632\u0627\u0631\u0629 "
            "\u0627\u0644\u062f\u0641\u0627\u0639 \u0628\u0645\u0648\u062c\u0628 "
            "\u0643\u062a\u0627\u0628\u0647\u0627 \u0627\u0644\u0645\u0631\u0642\u0645 "
            "\u0628\u0627\u0644\u0639\u062f\u062f (4/14482) \u0627\u0644\u0645\u0624\u0631\u062e "
            "\u0641\u064a 12/12/2024.\n"
            "\u0642\u0631\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 "
            "\u0641\u064a \u062c\u0644\u0633\u062a\u0647 \u0627\u0644\u0627\u0639\u062a\u064a\u0627\u062f\u064a\u0629 "
            "\u0627\u0644\u062b\u0627\u0644\u062b\u0629 \u0648\u0627\u0644\u062e\u0645\u0633\u064a\u0646 "
            "\u0627\u0644\u0645\u0646\u0639\u0642\u062f\u0629 \u0641\u064a 30/12/2024\n"
            "\u2022 \u0623\u0648\u0644\u064b\u0627: \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 "
            "\u0639\u0644\u0649 \u0627\u0633\u062a\u062b\u0646\u0627\u0621 \u0639\u0642\u062f "
            "\u062a\u0635\u0644\u064a\u062d \u0639\u0627\u0645 \u0634\u0627\u0645\u0644 "
            "\u0644\u0644\u0637\u0627\u0626\u0631\u0627\u062a \u0627\u0644\u0645\u0631\u0648\u062d\u064a\u0629 "
            "\u0646\u0648\u0639 MI-17 \u0628\u0639\u062f\u062f 15 \u0637\u0627\u0626\u0631\u0629 "
            "\u0628\u0645\u0628\u0644\u063a 115.442.307.79 \u062f\u0648\u0644\u0627\u0631.\n"
            "1. \u0627\u0644\u0645\u0627\u062f\u0629 (1) \u0645\u0646 \u0636\u0648\u0627\u0628\u0637 "
            "\u062a\u0646\u0641\u064a\u0630 \u0639\u0642\u0648\u062f \u0627\u0644\u062a\u0633\u0644\u064a\u062d.\n"
            "2. \u0627\u0644\u0645\u0627\u062f\u0629 (2/\u0623\u0648\u0644\u0627/\u062f) "
            "\u0645\u0646 \u062a\u0639\u0644\u064a\u0645\u0627\u062a \u062a\u0646\u0641\u064a\u0630 "
            "\u0627\u0644\u0639\u0642\u0648\u062f \u0627\u0644\u062d\u0643\u0648\u0645\u064a\u0629.\n"
            "\u2022 \u062b\u0627\u0646\u064a\u064b\u0627: \u062a\u062a\u062d\u0645\u0644 "
            "\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062f\u0641\u0627\u0639 "
            "\u0633\u0644\u0627\u0645\u0629 \u0627\u0644\u0625\u062c\u0631\u0627\u0621\u0627\u062a "
            "\u0627\u0644\u0642\u0627\u0646\u0648\u0646\u064a\u0629 \u0648\u0627\u0644\u0645\u0627\u0644\u064a\u0629.\n"
            "\u062f. \u062d\u0645\u064a\u062f \u0646\u0639\u064a\u0645 \u0627\u0644\u063a\u0632\u064a\n"
            "\u0627\u0644\u0623\u0645\u064a\u0646 \u0627\u0644\u0639\u0627\u0645 \u0644\u0645\u062c\u0644\u0633 "
            "\u0627\u0644\u0648\u0632\u0631\u0627\u0621\n31/12/2024"
        )
        results = {
            "documents": [[source_text]],
            "metadatas": [[
                {
                    "chunk_id": "uploaded-mi17",
                    "source_file": "uploaded_aaaaaaaaaaaaaaaa_mi17.pdf",
                    "document_upload_id": "aaaaaaaaaaaaaaaa",
                }
            ]],
        }

        answer = complete_uploaded_source_answer(
            "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 "
            "\u064a\u0642\u0636\u064a \u0628\u0623\u062e\u0630 \u0645\u0627 \u064a\u0642\u062a\u0636\u064a.",
            results,
        )

        self.assertIn("MI-17", answer)
        self.assertIn("115.442.307.79", answer)
        self.assertIn("\u062a\u062a\u062d\u0645\u0644 \u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062f\u0641\u0627\u0639", answer)
        self.assertTrue(answer.startswith("\u0628\u0646\u0627\u0621\u064b \u0639\u0644\u0649"))
        self.assertNotIn("\u0631\u0642\u0645 (99999)", answer)
        self.assertNotIn("\u062d\u0645\u064a\u062f \u0646\u0639\u064a\u0645", answer)
        self.assertEqual(
            exact_law_sources(results, registry={"by_chunk_id": {}}),
            ["\u0642\u0631\u0627\u0631 \u0627\u0633\u062a\u062b\u0646\u0627\u0621 \u0639\u0642\u062f \u062a\u0635\u0644\u064a\u062d \u0627\u0644\u0637\u0627\u0626\u0631\u0627\u062a \u0627\u0644\u0645\u0631\u0648\u062d\u064a\u0629"],
        )

    def test_routing_uploaded_page_does_not_replace_answer(self):
        routing_text = (
            "\u062f\u0627\u0626\u0631\u0629 \u0634\u0624\u0648\u0646 \u0645\u062c\u0644\u0633 "
            "\u0627\u0644\u0648\u0632\u0631\u0627\u0621\n"
            "\u0635\u0648\u0631\u0629 \u0639\u0646\u0647 \u0625\u0644\u0649:\n"
            "- \u0645\u0643\u062a\u0628 \u0631\u0626\u064a\u0633 \u0645\u062c\u0644\u0633 "
            "\u0627\u0644\u0648\u0632\u0631\u0627\u0621 / \u0644\u0644\u0627\u0637\u0644\u0627\u0639\u060c "
            "\u0645\u0639 \u0627\u0644\u062a\u0642\u062f\u064a\u0631.\n"
            "\u0627\u0644\u0645\u0631\u0627\u0641\u0642\u0627\u062a: \u0642\u0631\u0627\u0631 "
            "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621."
        )
        results = {
            "documents": [[routing_text]],
            "metadatas": [[
                {
                    "chunk_id": "routing-page",
                    "source_file": "uploaded_bbbbbbbbbbbbbbbb_finance.pdf",
                    "document_upload_id": "bbbbbbbbbbbbbbbb",
                }
            ]],
        }

        self.assertEqual(
            complete_uploaded_source_answer("short model answer", results),
            "short model answer",
        )

    def test_retrieved_documents_for_source_prefers_json_long_text(self):
        results = {
            "documents": [["SHORT CHUNK"]],
            "metadatas": [[{"source_file": "sample.docx"}]],
        }

        with patch(
            "app.rag_answer._source_text_for_source_file",
            return_value="PRIMARY LONG TEXT",
        ):
            self.assertEqual(
                _retrieved_documents_for_source(results, "sample.docx"),
                ["PRIMARY LONG TEXT"],
            )

    def test_retrieved_documents_for_source_does_not_use_chunk_as_full_text(self):
        results = {
            "documents": [["SHORT CHUNK"]],
            "metadatas": [[{"source_file": "sample.docx"}]],
        }

        with patch(
            "app.rag_answer._source_text_for_source_file",
            return_value="",
        ):
            self.assertEqual(_retrieved_documents_for_source(results, "sample.docx"), [])

    def test_full_document_context_detection_and_replacement(self):
        results = {
            "documents": [["SHORT CHUNK"]],
            "metadatas": [[{"source_file": "sample.docx"}]],
            "distances": [[0.2]],
        }

        self.assertTrue(wants_full_document_context("ما هو مضمون هذا القرار؟"))
        self.assertFalse(wants_full_document_context("كم أصبح سعر زيت الغاز؟"))

        with patch(
            "app.rag_answer._source_text_for_source_file",
            return_value="PRIMARY LONG TEXT",
        ):
            replaced = results_with_full_document_context(results)

        self.assertEqual(replaced["documents"], [["PRIMARY LONG TEXT"]])
        self.assertEqual(replaced["metadatas"][0][0]["retrieval_context"], "full_document")

    def test_decision_number_answer_does_not_use_reference_number(self):
        results = {
            "documents": [["قرار يتضمن توصية مرقمة 24315 ق"]],
            "metadatas": [[
                {
                    "chunk_id": "chunk-1",
                    "source_file": "sample.docx",
                    "document_number": "",
                    "decision_number": "",
                    "law_number": "",
                    "reference_numbers": "24315 ق",
                }
            ]],
        }

        result = decision_number_answer("ما رقم القرار؟", results)

        self.assertIsNotNone(result)
        self.assertEqual(result.content, MISSING_DECISION_NUMBER_ANSWER)

    def test_decision_number_answer_uses_only_decision_metadata(self):
        results = {
            "documents": [["قرار مجلس الوزراء"]],
            "metadatas": [[{"decision_number": "15", "reference_numbers": "24315 ق"}]],
        }

        result = decision_number_answer("ما رقم القرار؟", results)

        self.assertIsNotNone(result)
        self.assertEqual(result.content, "رقم القرار هو 15.")

    def test_title_only_answer_is_repaired_from_context(self):
        results = {
            "documents": [[
                "\u0661\u0662. \u0642\u0627\u0646\u0648\u0646 "
                "\u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0623\u0637\u0628\u0627\u0621 "
                "\u0631\u0642\u0645 (\u0661\u0661) \u0644\u0633\u0646\u0629 \u0662\u0660\u0661\u0663\n"
                "\u0627\u0644\u0645\u0627\u062f\u0629 (\u0661): "
                "\u064a\u0647\u062f\u0641 \u0627\u0644\u0642\u0627\u0646\u0648\u0646 "
                "\u0625\u0644\u0649 \u062d\u0645\u0627\u064a\u0629 "
                "\u0627\u0644\u0623\u0637\u0628\u0627\u0621 \u0645\u0646 "
                "\u0627\u0644\u0627\u0639\u062a\u062f\u0627\u0621\u0627\u062a "
                "\u0648\u0627\u0644\u0645\u0637\u0627\u0644\u0628\u0627\u062a "
                "\u0627\u0644\u0639\u0634\u0627\u0626\u0631\u064a\u0629."
            ]],
            "metadatas": [[{"chunk_id": "chunk-1"}]],
        }
        title = (
            "\u0642\u0627\u0646\u0648\u0646 \u062d\u0645\u0627\u064a\u0629 "
            "\u0627\u0644\u0623\u0637\u0628\u0627\u0621 \u0631\u0642\u0645 "
            "(\u0661\u0661) \u0644\u0633\u0646\u0629 \u0662\u0660\u0661\u0663"
        )

        self.assertTrue(is_legal_title_only(title))
        self.assertEqual(
            repair_empty_or_title_answer("\u0639\u0631\u0641 \u0642\u0627\u0646\u0648\u0646 \u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0623\u0637\u0628\u0627\u0621", title, results),
            "\u064a\u0647\u062f\u0641 \u0627\u0644\u0642\u0627\u0646\u0648\u0646 "
            "\u0625\u0644\u0649 \u062d\u0645\u0627\u064a\u0629 "
            "\u0627\u0644\u0623\u0637\u0628\u0627\u0621 \u0645\u0646 "
            "\u0627\u0644\u0627\u0639\u062a\u062f\u0627\u0621\u0627\u062a "
            "\u0648\u0627\u0644\u0645\u0637\u0627\u0644\u0628\u0627\u062a "
            "\u0627\u0644\u0639\u0634\u0627\u0626\u0631\u064a\u0629.",
        )

    def test_law_overview_prefers_reasons_from_context(self):
        results = {
            "documents": [[
                "\u0661\u0664. \u0642\u0627\u0646\u0648\u0646 "
                "\u0627\u0644\u0623\u0633\u0644\u062d\u0629 \u0631\u0642\u0645 "
                "(\u0665\u0661) \u0644\u0633\u0646\u0629 \u0662\u0660\u0661\u0667\n"
                "\u0627\u0644\u0623\u0633\u0628\u0627\u0628 "
                "\u0627\u0644\u0645\u0648\u062c\u0628\u0629: "
                "\u0625\u0644\u063a\u0627\u0621 \u0627\u0644\u0642\u0648\u0627\u0646\u064a\u0646 "
                "\u0648\u0627\u0644\u0623\u0648\u0627\u0645\u0631 "
                "\u0627\u0644\u0627\u0646\u062a\u0642\u0627\u0644\u064a\u0629 "
                "\u0627\u0644\u0633\u0627\u0628\u0642\u0629\u060c "
                "\u0648\u0648\u0636\u0639 \u062a\u0634\u0631\u064a\u0639 "
                "\u0648\u0637\u0646\u064a \u0635\u0627\u0631\u0645 "
                "\u0644\u062d\u0635\u0631 \u0627\u0644\u0633\u0644\u0627\u062d "
                "\u0628\u064a\u062f \u0627\u0644\u062f\u0648\u0644\u0629.\n"
                "\u0627\u0644\u0647\u064a\u0643\u0644 "
                "\u0627\u0644\u062a\u0646\u0638\u064a\u0645\u064a: "
                "\u064a\u062a\u0648\u0644\u0649 \u0648\u0632\u064a\u0631 "
                "\u0627\u0644\u062f\u0627\u062e\u0644\u064a\u0629 "
                "\u0625\u062f\u0627\u0631\u0629 \u0648\u062a\u0646\u0641\u064a\u0630 "
                "\u0623\u062d\u0643\u0627\u0645 \u0627\u0644\u0642\u0627\u0646\u0648\u0646.\n"
                "\u0627\u0644\u0645\u0627\u062f\u0629 (\u0664): "
                "\u064a\u064f\u0642\u0633\u0645 \u0627\u0644\u0633\u0644\u0627\u062d "
                "\u0625\u0644\u0649 \u062b\u0644\u0627\u062b\u0629 "
                "\u0623\u0646\u0648\u0627\u0639."
            ]],
            "metadatas": [[{"chunk_id": "chunk-1"}]],
        }

        answer = meaningful_answer_from_context(
            "\u0645\u0627 \u0647\u0648 \u0642\u0627\u0646\u0648\u0646 "
            "\u0627\u0644\u0623\u0633\u0644\u062d\u0629 \u0631\u0642\u0645 "
            "(\u0665\u0661) \u0644\u0633\u0646\u0629 \u0662\u0660\u0661\u0667\u061f",
            results,
        )

        self.assertIn(
            "\u0644\u062d\u0635\u0631 \u0627\u0644\u0633\u0644\u0627\u062d "
            "\u0628\u064a\u062f \u0627\u0644\u062f\u0648\u0644\u0629",
            answer,
        )
        self.assertNotIn("\u064a\u062a\u0648\u0644\u0649 \u0648\u0632\u064a\u0631", answer)

    def test_law_title_query_prefers_reasons_and_single_group_source(self):
        results = {
            "documents": [[
                "تفكيك القوانين من (١) إلى (١٠) - المبادئ الدستورية والجنائية\n"
                "١٣. قانون هيئة الحشد الشعبي رقم (٤٠) لسنة ٢٠١٦\n"
                "الأسباب الموجبة: إيجاد غطاء قانوني وتأسيسي ثابت للمقاتلين والفصائل المتطوعة عقب فتوى الدفاع الكفائي، وتنظيم ارتباطهم بالمنظومة الأمنية الرسمية لضمان حقوقهم وحقوق عوائل شهدائهم وجرحاهم.\n"
                "الهيكل التنظيمي: تأسيس هيئة الحشد الشعبي ككيان عسكري مستقل يرتبط مباشرة بالقائد العام للقوات المسلحة.",
                "٩. قانون مكافحة الإرهاب رقم (١٣) لسنة ٢٠٠٥",
            ]],
            "metadatas": [[{"chunk_id": "chunk-1"}, {"chunk_id": "chunk-2"}]],
        }
        title = "قانون هيئة الحشد الشعبي رقم (٤٠) لسنة ٢٠١٦"

        self.assertEqual(exact_law_sources(results, registry=REGISTRY), [SECTION_HEADING])
        self.assertEqual(
            repair_empty_or_title_answer(title, title, results),
            "إيجاد غطاء قانوني وتأسيسي ثابت للمقاتلين والفصائل المتطوعة عقب فتوى الدفاع الكفائي، وتنظيم ارتباطهم بالمنظومة الأمنية الرسمية لضمان حقوقهم وحقوق عوائل شهدائهم وجرحاهم.",
        )

    @patch("app.rag_answer.load_registry")
    @patch("app.rag_answer.filter_results_to_registered")
    def test_generate_answer_returns_insufficient_context_without_registered_chunks(
        self,
        mock_filter_results,
        mock_load_registry,
    ):
        mock_load_registry.return_value = {"by_chunk_id": {}}
        mock_filter_results.return_value = (
            {"documents": [[]], "metadatas": [[]]},
            ["Retrieved chunk 'chunk-1' is missing from citation_registry.json."],
        )

        result = generate_answer("question", RESULTS)

        self.assertIn(INSUFFICIENT_CONTEXT_MESSAGE, result.content)
        self.assertIn("لا توجد مصادر مطابقة", result.content)
        self.assertNotIn("Not specified", result.content)
        self.assertEqual(
            result.warnings,
            ["Retrieved chunk 'chunk-1' is missing from citation_registry.json."],
        )

    @patch("app.rag_answer.call_chat_model")
    @patch("app.rag_answer.load_registry")
    @patch("app.rag_answer.filter_results_to_registered")
    def test_generate_answer_rejects_unmatched_exact_decision_markers(
        self,
        mock_filter_results,
        mock_load_registry,
        mock_call_chat_model,
    ):
        registry = {
            "by_chunk_id": {
                "budget-chunk": {
                    "law_name": "\u0627\u0644\u0645\u0635\u0627\u062f\u0642\u0629 \u0639\u0644\u0649 \u0642\u0627\u0646\u0648\u0646 \u0627\u0644\u0645\u0648\u0627\u0632\u0646\u0629",
                    "source_file": "budget.pdf",
                    "chunk_id": "budget-chunk",
                }
            }
        }
        results = {
            "documents": [[
                "\u0627\u0644\u0645\u062c\u0644\u0629 \u0627\u0644\u0648\u0632\u0627\u0631\u064a\u0629 "
                "\u0627\u0644\u062b\u0627\u0644\u062b\u0629 \u0648\u0627\u0644\u062e\u0627\u0645\u0633\u0629 "
                "\u0639\u0634\u0631 \u0627\u0644\u0645\u0646\u0639\u0642\u062f\u0629 \u0641\u064a "
                "30/12/2024 \u0628\u0634\u0623\u0646 \u0627\u0644\u0645\u0648\u0627\u0632\u0646\u0629."
            ]],
            "metadatas": [[{"chunk_id": "budget-chunk", "source_file": "budget.pdf"}]],
            "distances": [[0.2]],
        }
        mock_load_registry.return_value = registry
        mock_filter_results.return_value = (results, [])

        result = generate_answer(
            "\u0642\u0631\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621 "
            "\u0641\u064a 30/12/2024 \u0628\u0634\u0623\u0646 MI-17 \u0648\u0634\u0631\u0643\u0629 AAL",
            results,
        )

        self.assertIn(INSUFFICIENT_CONTEXT_MESSAGE, result.content)
        self.assertIn("لا توجد مصادر مطابقة", result.content)
        self.assertNotIn("The retrieved legal sources", result.content)
        self.assertIn("MI-17", result.warnings[-1])
        self.assertIn("AAL", result.warnings[-1])
        mock_call_chat_model.assert_not_called()

    @patch("app.ui.generate_answer")
    @patch("app.ui.search")
    def test_streamlit_answer_uses_shared_answer_and_warnings(
        self,
        mock_search,
        mock_generate,
    ):
        mock_search.return_value = RESULTS
        mock_generate.return_value = AnswerResult(
            content="testable answer",
            warnings=["citation warning"],
        )

        message = answer_question("legal question")

        self.assertEqual(message["content"], "testable answer")
        self.assertEqual(message["warnings"], ["citation warning"])
        self.assertEqual(message["snippets"][0]["source_file"], "law.pdf")


if __name__ == "__main__":
    unittest.main()
