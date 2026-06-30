"""Focused validation and protected settings API tests."""

import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

from app.api import app
from app.settings_schema import SettingsValidationError, validate_settings


class SettingsValidationTests(unittest.TestCase):
    def test_accepts_normalized_retrieval_weights(self):
        result = validate_settings(
            {"retrieval": {"semantic_weight": 0.6, "keyword_weight": 0.4}}
        )
        self.assertEqual(result["retrieval"]["semantic_weight"], 0.6)

    def test_rejects_overlap_not_smaller_than_chunk(self):
        with self.assertRaises(SettingsValidationError) as context:
            validate_settings(
                {"retrieval": {"chunk_size": 500, "chunk_overlap": 500}}
            )
        self.assertIn("retrieval.chunk_overlap", context.exception.errors)

    def test_rejects_unnormalized_weights(self):
        with self.assertRaises(SettingsValidationError) as context:
            validate_settings(
                {"retrieval": {"semantic_weight": 0.8, "keyword_weight": 0.4}}
            )
        self.assertIn("retrieval.weights", context.exception.errors)

    def test_rejects_unknown_fields_that_could_expose_secrets(self):
        with self.assertRaises(SettingsValidationError):
            validate_settings({"model": {"database_password": "secret"}})

    def test_rejects_invalid_fine_tuning_schedule_time(self):
        with self.assertRaises(SettingsValidationError) as context:
            validate_settings({"fine_tuning": {"scheduled_start_time": "25:99"}})
        self.assertIn("fine_tuning.scheduled_start_time", context.exception.errors)


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.settings_api.admin_for_token", return_value=None)
    def test_settings_requires_administrator(self, _mock_admin):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "unauthorized")

    @patch("app.settings_api.get_settings")
    @patch("app.settings_api.admin_for_token", return_value={"id": 1, "username": "admin"})
    def test_settings_response_contains_no_password(self, _mock_admin, mock_get):
        mock_get.return_value = {"model": {"chat_model": "qwen2.5:7b"}}
        response = self.client.get(
            "/api/settings", cookies={"legal_admin_session": "test"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password", response.text.lower())

    @patch("app.settings_api.update_settings")
    @patch("app.settings_api.admin_for_token", return_value={"id": 1, "username": "admin", "permissions": ["manage_settings"]})
    def test_settings_update(self, _mock_admin, mock_update):
        mock_update.return_value = {"appearance": {"language": "en"}}
        response = self.client.put(
            "/api/settings",
            json={"appearance": {"language": "en"}},
            cookies={"legal_admin_session": "test"},
        )
        self.assertEqual(response.status_code, 200)
        mock_update.assert_called_once()

    @patch("app.settings_api.ollama.Client")
    @patch("app.settings_api.get_settings")
    @patch("app.settings_api.admin_for_token", return_value={"id": 1, "username": "admin", "permissions": ["manage_settings"]})
    def test_model_connection_failure_is_reported(
        self, _mock_admin, mock_get, mock_client
    ):
        mock_get.return_value = {
            "model": {
                "ollama_base_url": "http://127.0.0.1:11434",
                "request_timeout": 5,
            }
        }
        mock_client.return_value.list.side_effect = OSError("offline")
        response = self.client.post(
            "/api/settings/model/test",
            json={},
            cookies={"legal_admin_session": "test"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "ollama_unavailable")


if __name__ == "__main__":
    unittest.main()
