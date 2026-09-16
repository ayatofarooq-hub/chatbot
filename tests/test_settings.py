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
            validate_settings({"model": {"secret_password": "secret"}})

    def test_rejects_invalid_fine_tuning_schedule_time(self):
        with self.assertRaises(SettingsValidationError) as context:
            validate_settings({"fine_tuning": {"scheduled_start_time": "25:99"}})
        self.assertIn("fine_tuning.scheduled_start_time", context.exception.errors)

    def test_accepts_supported_upload_file_sizes(self):
        for size in (5, 10, 20, 25):
            result = validate_settings({"upload": {"max_file_size_mb": size}})
            self.assertEqual(result["upload"]["max_file_size_mb"], size)

    def test_accepts_central_kurdish_interface_language(self):
        result = validate_settings({"appearance": {"language": "ckb"}})
        self.assertEqual(result["appearance"]["language"], "ckb")

        kurmanji = validate_settings({"appearance": {"language": "ku"}})
        self.assertEqual(kurmanji["appearance"]["language"], "ku")

    def test_rejects_unsupported_upload_file_size(self):
        with self.assertRaises(SettingsValidationError) as context:
            validate_settings({"upload": {"max_file_size_mb": 30}})
        self.assertIn("upload.max_file_size_mb", context.exception.errors)


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

    @patch("app.runtime_settings.runtime_settings")
    @patch("app.api.authenticated_admin", return_value={"id": 1, "username": "admin"})
    def test_upload_settings_endpoint_returns_upload_limits(self, _mock_admin, mock_runtime_settings):
        mock_runtime_settings.return_value = {
            "upload": {"max_file_count": 10, "max_file_size_mb": 25}
        }
        response = self.client.get(
            "/api/uploads/settings", cookies={"legal_admin_session": "test"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"max_file_count": 10, "max_file_size_mb": 25}
        )

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

    @patch("app.settings_api.audit_log")
    @patch("app.settings_api.audit_log_count", return_value=37)
    @patch(
        "app.settings_api.admin_for_token",
        return_value={
            "id": 1,
            "username": "admin",
            "permissions": ["view_audit_log"],
        },
    )
    def test_audit_log_pagination(
        self,
        _mock_admin,
        _mock_count,
        mock_audit_log,
    ):
        mock_audit_log.return_value = [{"id": 16}]

        response = self.client.get(
            "/api/settings/audit-log?page=2&page_size=15",
            cookies={"legal_admin_session": "test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["total_pages"], 3)
        self.assertEqual(response.json()["total"], 37)
        mock_audit_log.assert_called_once_with(15, 15)

    @patch(
        "app.settings_api.admin_for_token",
        return_value={
            "id": 1,
            "username": "admin",
            "permissions": ["view_audit_log"],
        },
    )
    def test_audit_log_rejects_invalid_page(self, _mock_admin):
        response = self.client.get(
            "/api/settings/audit-log?page=bad",
            cookies={"legal_admin_session": "test"},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
