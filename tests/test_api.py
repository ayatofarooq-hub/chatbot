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
        self.assertIn('id="ai-character-fallback"', response.text)
        self.assertIn("effendi-flipbook.js", response.text)
        self.assertIn("شخصية مُجيب الكارتونية بكامل الجسم", response.text)
        self.assertIn('class="landing-intro" dir="rtl"', response.text)
        self.assertLess(
            response.text.index('class="landing-intro-copy"'),
            response.text.index('class="landing-effendi-welcome"'),
        )
        self.assertLess(
            response.text.index('class="landing-prompt-body"'),
            response.text.index('class="landing-effendi-welcome"'),
        )
        self.assertLess(
            response.text.index('class="landing-effendi-welcome"'),
            response.text.index('class="landing-prompt-actions"'),
        )
        self.assertIn("وياك مُجيب، تفضل بشنو أكدر أساعدك!", response.text)
        self.assertNotIn("النموذج المحلي · Ollama", response.text)
        self.assertNotIn('id="review-nav-button"', response.text)
        self.assertNotIn('id="assistant-language"', response.text)
        self.assertNotIn("Kurdî (Kurmancî)", response.text)
        self.assertIn('id="ai-audio-settings"', response.text)
        self.assertIn('id="ai-character-sliders"', response.text)
        self.assertIn('class="ai-character-dock ai-character-dock--static"', response.text)
        self.assertNotIn('id="ai-character-puppet"', response.text)
        self.assertNotIn('id="ai-effendi-3d"', response.text)
        self.assertNotIn('src="/assets/effendi-3d.js', response.text)

    def test_frontend_assets(self):
        response = self.client.get("/assets/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("--green", response.text)
        self.assertIn("--landing-content-width: min(840px, 100%)", response.text)
        self.assertIn("width: var(--landing-content-width)", response.text)
        self.assertIn(".landing-prompt-body", response.text)
        self.assertIn("body.chat-sidebar-enabled.chat-sidebar-collapsed .application", response.text)
        self.assertIn(".model-settings-card", response.text)
        self.assertIn("--night-page: #101a17", response.text)
        self.assertIn("--night-sidebar-left: #172520", response.text)
        self.assertIn("--night-sidebar-right: #143d30", response.text)
        self.assertIn("--night-card: #1c2b25", response.text)
        self.assertIn("--night-border: #34483d", response.text)
        self.assertIn("--night-text: #f2f4ef", response.text)
        self.assertIn("--night-text-muted: #b5c3b9", response.text)
        self.assertIn("--night-interactive: #21704e", response.text)
        self.assertIn("--night-gold: #d4ad32", response.text)
        self.assertIn('[data-theme="dark"] .landing-suggestions button', response.text)
        self.assertIn("body.chat-sidebar-enabled .chat-history-sidebar", response.text)
        self.assertIn('[data-theme="dark"] .settings-login-input', response.text)
        self.assertIn('[data-theme="dark"] .upload-dropzone', response.text)
        self.assertIn('[data-theme="dark"] .priority-options button.selected', response.text)
        self.assertIn('[data-theme="dark"] .stat-card', response.text)

        script_response = self.client.get("/assets/app.js")
        self.assertEqual(script_response.status_code, 200)
        self.assertIn('fetch("/ask"', script_response.text)
        self.assertIn('fetch("/api/tts"', script_response.text)
        self.assertIn("httpErrorMessage(response.status", script_response.text)
        self.assertIn("وياك مُجيب، تفضل بشنو أكدر أساعدك!", script_response.text)
        self.assertIn("20260923-model-selection-v1", script_response.text)
        new_chat_start = script_response.text.index("function startNewConversation()")
        new_chat_end = script_response.text.index("\n}", new_chat_start)
        new_chat_handler = script_response.text[new_chat_start:new_chat_end]
        self.assertIn('showView("landing")', new_chat_handler)
        self.assertNotIn('showView("assistant")', new_chat_handler)
        self.assertIn("20260923-hide-review-nav-v1", self.client.get("/").text)
        self.assertIn('id="ai-speech-stop"', self.client.get("/").text)

        error_messages_response = self.client.get("/assets/http-errors.js")
        self.assertEqual(error_messages_response.status_code, 200)
        expected_http_errors = {
            400: "الطلب غير صحيح. يُرجى مراجعة البيانات المدخلة.",
            401: "يُرجى تسجيل الدخول للمتابعة.",
            403: "ليس لديك صلاحية لتنفيذ هذا الإجراء.",
            404: "العنصر المطلوب غير موجود.",
            408: "انتهت مهلة الطلب. يُرجى المحاولة مرة أخرى.",
            409: "تعذّر إكمال العملية بسبب تعارض في البيانات.",
            422: "بعض البيانات المدخلة غير صحيحة. يُرجى مراجعتها.",
            429: "أُرسلت طلبات كثيرة. يُرجى الانتظار قليلًا.",
            500: "حدث خطأ غير متوقع. يُرجى المحاولة لاحقًا.",
            502: "الخدمة غير متاحة مؤقتًا. يُرجى المحاولة لاحقًا.",
            503: "الخدمة غير متاحة حاليًا. يُرجى المحاولة لاحقًا.",
            504: "تأخرت استجابة الخادم. يُرجى المحاولة مرة أخرى.",
        }
        for status_code, message in expected_http_errors.items():
            self.assertIn(f'{status_code}: "{message}"', error_messages_response.text)

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

    @patch("app.api.voice_status")
    def test_tts_status_reports_local_voice(self, mock_status):
        mock_status.return_value = {
            "available": True,
            "engine": "sherpa-onnx",
            "voice": "Kareem",
            "offline": True,
        }

        response = self.client.get("/api/tts/status")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["available"])
        self.assertTrue(response.json()["offline"])

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.synthesize_arabic", return_value=b"RIFF-local-audio")
    def test_tts_returns_local_wav(self, mock_synthesize, _mock_admin):
        response = self.client.post(
            "/api/tts",
            json={"text": "مرحباً بكم", "speed": 0.96},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(response.content, b"RIFF-local-audio")
        mock_synthesize.assert_called_once_with("مرحباً بكم", 0.96)

    @patch("app.auth.admin_for_token", return_value=None)
    def test_tts_requires_authentication(self, _mock_admin):
        response = self.client.post("/api/tts", json={"text": "مرحباً"})

        self.assertEqual(response.status_code, 401)

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
        mock_answer_question.assert_called_once_with("سؤال", False, None, "ar")

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.answer_question")
    def test_ask_forwards_kurmanji_response_language(self, mock_answer_question, _mock_admin):
        mock_answer_question.return_value = {
            "question": "Pirs",
            "answer": "Bersiv",
            "sources": [],
            "warnings": [],
            "citations": [],
            "snippets": [],
        }

        response = self.client.post(
            "/ask",
            json={"question": "Pirs", "response_language": "ku"},
        )

        self.assertEqual(response.status_code, 200)
        mock_answer_question.assert_called_once_with("Pirs", True, None, "ku")

    @patch("app.auth.admin_for_token", return_value={"id": 1, "username": "admin"})
    @patch("app.api.synthesize_kurmanji", return_value=b"RIFF-kurmanji-audio")
    def test_tts_returns_kurmanji_wav(self, mock_synthesize, _mock_admin):
        response = self.client.post(
            "/api/tts",
            json={"text": "Silav, ez Mucib im.", "language": "ku", "rate": 1.0},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"RIFF-kurmanji-audio")
        mock_synthesize.assert_called_once_with("Silav, ez Mucib im.", 1.0)

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

    def test_source_hint_applies_only_to_follow_up_questions(self):
        results = {
            "documents": [["previous doc text", "new legal text"]],
            "metadatas": [[
                {"chunk_id": "previous", "source_file": "previous.docx", "document_id": "doc-1"},
                {"chunk_id": "new", "source_file": "new-law.docx", "document_id": "doc-2"},
            ]],
            "distances": [[0.1, 0.2]],
            "relevance_scores": [[0.9, 0.8]],
            "intent_scores": [[0.3, 0.7]],
        }
        hint = {"sources": [{"filename": "previous.docx"}]}

        follow_up = api_module.filter_results_by_source_hint(
            results,
            hint,
            "ما تاريخ هذا الكتاب؟",
        )
        new_topic = api_module.filter_results_by_source_hint(
            results,
            hint,
            "ما عقوبة جريمة السرقة؟",
        )

        self.assertEqual(follow_up["documents"], [["previous doc text"]])
        self.assertEqual(follow_up["intent_scores"], [[0.3]])
        self.assertEqual(new_topic["documents"], results["documents"])

    def test_question_document_filter_keeps_named_word_source(self):
        results = {
            "documents": [["defense chunk", "foreign chunk", "defense second chunk"]],
            "metadatas": [[
                {
                    "chunk_id": "defense-1",
                    "source_file": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                    "document_id": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                },
                {
                    "chunk_id": "foreign-1",
                    "source_file": "الخارجية قرار الجرحى الفلسطينين.docx",
                    "document_id": "الخارجية قرار الجرحى الفلسطينين.docx",
                },
                {
                    "chunk_id": "defense-2",
                    "source_file": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                    "document_id": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                },
            ]],
            "distances": [[0.1, 0.2, 0.3]],
            "relevance_scores": [[0.9, 0.8, 0.7]],
        }

        filtered = api_module.filter_results_by_question_document(
            results,
            "ما مضمون ملف الدفاع الخاص بعقد تصليح الطائرات؟",
        )

        self.assertEqual(filtered["documents"], [["defense chunk", "defense second chunk"]])
        self.assertEqual(filtered["relevance_scores"], [[0.9, 0.7]])
        self.assertEqual(
            filtered["document_filter"]["source"],
            "الدفاع قرار استثناء عقد تصليح طائرات.docx",
        )

    def test_question_document_filter_ignores_generic_questions(self):
        results = {
            "documents": [["first chunk", "second chunk"]],
            "metadatas": [[
                {"chunk_id": "first", "source_file": "الدفاع قرار استثناء عقد تصليح طائرات.docx"},
                {"chunk_id": "second", "source_file": "الخارجية قرار الجرحى الفلسطينين.docx"},
            ]],
        }

        filtered = api_module.filter_results_by_question_document(
            results,
            "ما رقم القرار؟",
        )

        self.assertEqual(filtered["documents"], results["documents"])

    def test_results_for_question_document_loads_all_named_word_chunks(self):
        records = [
            {
                "id": "defense-2",
                "source_file": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                "document_id": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                "chunk_index": 1,
                "text": "second defense chunk",
            },
            {
                "id": "foreign-1",
                "source_file": "الخارجية قرار الجرحى الفلسطينين.docx",
                "document_id": "الخارجية قرار الجرحى الفلسطينين.docx",
                "chunk_index": 0,
                "text": "foreign chunk",
            },
            {
                "id": "defense-1",
                "source_file": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                "document_id": "الدفاع قرار استثناء عقد تصليح طائرات.docx",
                "chunk_index": 0,
                "text": "first defense chunk",
            },
        ]

        results = api_module.results_for_question_document(
            "اشرح ملف الدفاع عقد تصليح الطائرات",
            records,
        )

        self.assertEqual(
            results["documents"],
            [["first defense chunk", "second defense chunk"]],
        )
        self.assertEqual(results["metadatas"][0][0]["chunk_id"], "defense-1")
        self.assertEqual(
            results["document_filter"]["source"],
            "الدفاع قرار استثناء عقد تصليح طائرات.docx",
        )

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
