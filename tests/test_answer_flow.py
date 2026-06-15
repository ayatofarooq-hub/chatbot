"""Tests for citation-vetting behavior shared by CLI and Streamlit."""

import unittest
from unittest.mock import patch

from app.rag_answer import AnswerResult, generate_answer
from app.ui import answer_question


RESULTS = {
    "documents": [["نص قانوني مسترجع"]],
    "metadatas": [[{"source_file": "law.pdf", "page_number": 1}]],
    "distances": [[0.1]],
}


class AnswerFlowTests(unittest.TestCase):
    @patch("app.rag_answer.validate_answer")
    @patch("app.rag_answer.call_chat_model")
    def test_generate_answer_returns_failed_vetting_as_warnings(
        self,
        mock_call_chat_model,
        mock_validate_answer,
    ):
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
