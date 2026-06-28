"""Tests for the Postman-compatible chatbot API."""

import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from app.api import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_frontend(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("المساعد القانوني العراقي", response.text)

    def test_frontend_assets(self):
        response = self.client.get("/assets/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("--green", response.text)

        script_response = self.client.get("/assets/app.js")
        self.assertEqual(script_response.status_code, 200)
        self.assertIn('fetch("/ask"', script_response.text)

    def test_favicon_request_is_acknowledged(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 204)

    def test_ask_rejects_empty_question(self):
        response = self.client.post("/ask", json={"question": "  "})

        self.assertEqual(response.status_code, 422)

    @patch("app.api.answer_question")
    def test_ask_returns_answer_payload(self, mock_answer_question):
        mock_answer_question.return_value = {
            "question": "سؤال",
            "answer": "إجابة",
            "warnings": [],
            "citations": [],
            "snippets": [],
        }

        response = self.client.post(
            "/ask",
            json={"question": "سؤال", "include_snippets": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "إجابة")
        mock_answer_question.assert_called_once_with("سؤال", False)

    @patch("app.api.generate_answer")
    @patch("app.api.search")
    @patch("app.api.load_registry")
    def test_answer_question_returns_registry_citations(
        self,
        mock_load_registry,
        mock_search,
        mock_generate_answer,
    ):
        mock_search.return_value = {
            "documents": [["legal text"]],
            "metadatas": [[
                {
                    "chunk_id": "abc123",
                    "source_file": "penal_code.docx",
                    "page_number": 4,
                }
            ]],
            "distances": [[0.1]],
            "relevance_scores": [[0.9]],
            "bm25_scores": [[1.0]],
        }
        mock_load_registry.return_value = {
            "by_chunk_id": {
                "abc123": {
                    "law": "penal law",
                    "article": "article 405",
                    "document_type": "law",
                    "source_file": "penal_code.docx",
                    "ingest_date": "2026-06-11",
                    "chunk_id": "abc123",
                }
            }
        }
        mock_generate_answer.return_value.content = "answer"
        mock_generate_answer.return_value.warnings = []

        response = self.client.post(
            "/ask",
            json={"question": "question", "include_snippets": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["citations"],
            [
                {
                    "law": "penal law",
                    "article": "article 405",
                    "document_type": "law",
                    "source_file": "penal_code.docx",
                    "ingest_date": "2026-06-11",
                    "chunk_id": "abc123",
                }
            ],
        )

    def test_filesystem_document_routes_are_removed(self):
        self.assertEqual(self.client.get("/documents").status_code, 404)
        self.assertEqual(
            self.client.post("/documents", json={}).status_code,
            404,
        )
        self.assertEqual(
            self.client.put("/documents/law.txt", json={}).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete("/documents/law.txt").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
