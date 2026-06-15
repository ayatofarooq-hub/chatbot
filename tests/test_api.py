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

    @patch("app.api.list_documents")
    def test_list_documents(self, mock_list_documents):
        mock_list_documents.return_value = [
            {"filename": "law.txt", "size_bytes": 10}
        ]

        response = self.client.get("/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documents"][0]["filename"], "law.txt")

    @patch("app.api.insert_document")
    def test_insert_document(self, mock_insert_document):
        mock_insert_document.return_value = {
            "filename": "law.txt",
            "chunk_count": 1,
        }

        response = self.client.post(
            "/documents",
            json={"filename": "law", "content": "legal text"},
        )

        self.assertEqual(response.status_code, 201)
        mock_insert_document.assert_called_once_with("law", "legal text")

    @patch("app.api.update_document")
    def test_update_document(self, mock_update_document):
        mock_update_document.return_value = {
            "filename": "law.txt",
            "chunk_count": 1,
        }

        response = self.client.put(
            "/documents/law.txt",
            json={"content": "updated legal text"},
        )

        self.assertEqual(response.status_code, 200)
        mock_update_document.assert_called_once_with(
            "law.txt",
            "updated legal text",
        )

    @patch("app.api.delete_document")
    def test_delete_document(self, mock_delete_document):
        mock_delete_document.return_value = {
            "filename": "law.txt",
            "deleted": True,
        }

        response = self.client.delete("/documents/law.txt")

        self.assertEqual(response.status_code, 200)
        mock_delete_document.assert_called_once_with("law.txt")


if __name__ == "__main__":
    unittest.main()
