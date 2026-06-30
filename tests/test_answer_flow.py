"""Tests for citation-vetting behavior shared by CLI and Streamlit."""

import unittest
from unittest.mock import patch

from app.rag_answer import AnswerResult, generate_answer
from app.ui import answer_question


RESULTS = {
    "documents": [["نص قانوني مسترجع"]],
    "metadatas": [[{"chunk_id": "chunk-1", "source_file": "law.pdf", "page_number": 1}]],
    "distances": [[0.1]],
}


class AnswerFlowTests(unittest.TestCase):
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
        mock_load_registry.return_value = {
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
        mock_filter_results.return_value = (RESULTS, [])
        mock_call_chat_model.side_effect = ["الإجابة الأولى", "الإجابة المصححة"]
        mock_validate_answer.side_effect = [
            ["الفقرة 1 لا تحتوي على استشهاد."],
            ["الفقرة 1 لا تحتوي على استشهاد."],
        ]

        result = generate_answer("السؤال", RESULTS)

        self.assertEqual(
            result,
            AnswerResult(
                content="الإجابة المصححة",
                warnings=["الفقرة 1 لا تحتوي على استشهاد."],
            ),
        )
        self.assertEqual(mock_call_chat_model.call_count, 2)

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

        result = generate_answer("السؤال", RESULTS)

        self.assertIn("لا أملك نصا قانونيا كافيا", result.content)
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
            content="إجابة قابلة للاختبار",
            warnings=["تحذير استشهاد"],
        )

        message = answer_question("سؤال قانوني")

        self.assertEqual(message["content"], "إجابة قابلة للاختبار")
        self.assertEqual(message["warnings"], ["تحذير استشهاد"])
        self.assertEqual(message["snippets"][0]["source_file"], "law.pdf")


if __name__ == "__main__":
    unittest.main()
