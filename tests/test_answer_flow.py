"""Tests for citation-vetting behavior shared by CLI and Streamlit."""

import unittest
from unittest.mock import patch

import httpx

from app.legal_lookup import answer_exact_law
from app.prompts import INSUFFICIENT_CONTEXT_MESSAGE
from app.rag_answer import (
    AnswerResult,
    ensure_answer_citations,
    exact_law_sources,
    generate_answer,
    get_quick_response,
    is_legal_title_only,
    meaningful_answer_from_context,
    repair_empty_or_title_answer,
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
        self.assertEqual(
            result.warnings,
            ["Retrieved chunk 'chunk-1' is missing from citation_registry.json."],
        )

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
