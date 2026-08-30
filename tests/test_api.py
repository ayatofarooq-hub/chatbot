"""Tests for the Postman-compatible chatbot API."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from starlette.testclient import TestClient

import app.api as api_module
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

    def test_chat_history_is_persisted_on_server(self):
        payload = {
            "activeConversationId": "conversation-1",
            "conversations": [
                {
                    "id": "conversation-1",
                    "title": "test",
                    "messages": [{"role": "user", "content": "question"}],
                }
            ],
        }

        with TemporaryDirectory() as temporary_directory:
            history_file = Path(temporary_directory) / "chat_history.json"
            with patch.object(api_module, "CHAT_HISTORY_FILE", history_file):
                save_response = self.client.post("/api/chat-history", json=payload)
                load_response = self.client.get("/api/chat-history")

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(load_response.status_code, 200)
        self.assertEqual(load_response.json()["activeConversationId"], "conversation-1")
        self.assertEqual(load_response.json()["conversations"][0]["messages"][0]["content"], "question")

    def test_favicon_request_is_acknowledged(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 204)

    @patch("app.api.transcribe_audio", return_value="ما هي المادة القانونية")
    def test_transcribe_returns_arabic_text(self, mock_transcribe):
        response = self.client.post(
            "/transcribe",
            files={"audio": ("recording.webm", b"audio", "audio/webm")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"text": "ما هي المادة القانونية", "language": "ar"},
        )
        mock_transcribe.assert_called_once()

    def test_transcribe_rejects_unsupported_audio(self):
        response = self.client.post(
            "/transcribe",
            files={"audio": ("recording.txt", b"audio", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)

    @patch("app.auth.admin_for_token", return_value=None)
    def test_ask_requires_authentication(self, _mock_admin):
        response = self.client.post("/ask", json={"question": "question"})

        self.assertEqual(response.status_code, 401)

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    def test_ask_rejects_empty_question(self, _mock_admin):
        response = self.client.post("/ask", json={"question": "  "})

        self.assertEqual(response.status_code, 422)

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.answer_question")
    def test_ask_returns_answer_payload(self, mock_answer_question, _mock_admin):
        mock_answer_question.return_value = {
            "question": "سؤال",
            "answer": "إجابة",
            "sources": [],
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
        mock_answer_question.assert_called_once_with("سؤال", False, None)

    def test_filter_results_by_source_hint_keeps_same_document(self):
        results = {
            "documents": [["first text", "second text"]],
            "metadatas": [[
                {"chunk_id": "first", "source_file": "first.docx", "document_id": "doc-1"},
                {"chunk_id": "second", "source_file": "second.docx", "document_id": "doc-2"},
            ]],
            "distances": [[0.1, 0.2]],
            "relevance_scores": [[0.9, 0.6]],
        }

        filtered = api_module.filter_results_by_source_hint(
            results,
            {"sources": [{"filename": "second.docx"}]},
        )

        self.assertEqual(filtered["documents"], [["second text"]])
        self.assertEqual(filtered["metadatas"][0][0]["document_id"], "doc-2")
        self.assertEqual(filtered["relevance_scores"], [[0.6]])

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.legal_rag_answer_from_results")
    @patch("app.api.search")
    @patch("app.api.load_registry")
    def test_answer_question_returns_legal_rag_sources_and_registry_citations(
        self,
        mock_load_registry,
        mock_search,
        mock_legal_answer,
        _mock_admin,
    ):
        mock_search.return_value = {
            "documents": [["legal text"]],
            "metadatas": [[
                {
                    "chunk_id": "abc123",
                    "document_id": "legal_json_abc",
                    "source_file": "penal_code.docx",
                    "document_type": "law",
                    "year": "1969",
                    "issue_date": "1969-01-01",
                    "section": "article 405",
                    "item_number": "405",
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
                    "law_number": "111",
                    "law_year": "1969",
                    "article_number": "405",
                    "law_name": "Penal Code",
                    "classification": "criminal",
                    "document_type": "law",
                    "source_file": "penal_code.docx",
                    "ingest_date": "2026-06-11",
                    "chunk_id": "abc123",
                }
            }
        }
        mock_legal_answer.return_value = {
            "answer": "answer",
            "sources": [
                {
                    "document": "penal_code.docx",
                    "section": "article 405",
                    "item": "405",
                    "chunk_id": "abc123",
                }
            ],
            "confidence": 0.9,
        }

        response = self.client.post(
            "/ask",
            json={"question": "question", "include_snippets": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "answer")
        self.assertEqual(
            response.json()["sources"],
            [
                {
                    "document_id": "legal_json_abc",
                    "filename": "penal_code.docx",
                    "document_type": "law",
                    "year": "1969",
                    "issue_date": "1969-01-01",
                    "relevance_score": 0.9,
                }
            ],
        )
        self.assertEqual(
            response.json()["citations"],
            [
                {
                    "law": "penal law",
                    "article": "article 405",
                    "law_number": "111",
                    "law_year": "1969",
                    "article_number": "405",
                    "law_name": "Penal Code",
                    "classification": "criminal",
                    "document_type": "law",
                    "source_file": "penal_code.docx",
                    "ingest_date": "2026-06-11",
                    "chunk_id": "abc123",
                }
            ],
        )

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.legal_rag_answer_from_results")
    @patch("app.api.search")
    @patch("app.api.load_registry")
    def test_answer_question_deduplicates_sources_by_original_json_document(
        self,
        mock_load_registry,
        mock_search,
        mock_legal_answer,
        _mock_admin,
    ):
        mock_search.return_value = {
            "documents": [["first chunk", "second chunk"]],
            "metadatas": [[
                {
                    "chunk_id": "chunk-1",
                    "document_id": "legal_json_doc",
                    "source_file": "decision.docx",
                    "document_type": "قرار مجلس الوزراء",
                    "year": "2024",
                    "issue_date": "30/10/2024",
                },
                {
                    "chunk_id": "chunk-2",
                    "document_id": "legal_json_doc",
                    "source_file": "decision.docx",
                    "document_type": "قرار مجلس الوزراء",
                    "year": "2024",
                    "issue_date": "30/10/2024",
                },
            ]],
            "distances": [[0.1, 0.2]],
            "relevance_scores": [[0.94, 0.81]],
        }
        mock_load_registry.return_value = {
            "by_chunk_id": {
                "chunk-1": {"chunk_id": "chunk-1"},
                "chunk-2": {"chunk_id": "chunk-2"},
            }
        }
        mock_legal_answer.return_value = {
            "answer": "answer",
            "sources": [
                {"document": "decision.docx", "chunk_id": "chunk-1"},
                {"document": "decision.docx", "chunk_id": "chunk-2"},
            ],
            "confidence": 0.9,
        }

        response = self.client.post(
            "/ask",
            json={"question": "question", "include_snippets": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sources"],
            [
                {
                    "document_id": "legal_json_doc",
                    "filename": "decision.docx",
                    "document_type": "قرار مجلس الوزراء",
                    "year": "2024",
                    "issue_date": "30/10/2024",
                    "relevance_score": 0.94,
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

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.list_uploaded_documents")
    def test_uploaded_documents_are_listed(self, mock_list, _mock_admin):
        mock_list.return_value = [{"id": "abc", "name": "law.txt"}]

        response = self.client.get("/api/uploads")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], "abc")

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.create_uploaded_document")
    def test_uploaded_document_is_sent_to_indexing_service(
        self,
        mock_create,
        _mock_admin,
    ):
        mock_create.return_value = {
            "id": "abc",
            "name": "law.txt",
            "status": "indexed",
        }

        response = self.client.post(
            "/api/uploads",
            files={"file": ("law.txt", "نص قانوني".encode(), "text/plain")},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "indexed")
        mock_create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
