"""Tests for GPU-aware local model selection."""

import unittest
from unittest.mock import patch

from app.model_selection import detect_hardware_profile, recommend_model
from app.runtime_settings import runtime_settings


class ModelSelectionTests(unittest.TestCase):
    def test_recommends_model_by_available_vram(self):
        self.assertEqual(recommend_model(None), "qwen2.5:1.5b")
        self.assertEqual(recommend_model(2048), "qwen2.5:1.5b")
        self.assertEqual(recommend_model(4096), "qwen2.5:3b")
        self.assertEqual(recommend_model(8192), "qwen2.5:7b")

    @patch("app.model_selection._detect_windows_gpu", return_value=None)
    @patch(
        "app.model_selection._detect_nvidia",
        return_value=("NVIDIA Test GPU", 12288, "nvidia-smi"),
    )
    def test_detected_gpu_is_reported(self, _nvidia, _windows):
        profile = detect_hardware_profile()

        self.assertTrue(profile["gpu_detected"])
        self.assertEqual(profile["gpu_name"], "NVIDIA Test GPU")
        self.assertEqual(profile["recommended_model"], "qwen2.5:7b")

    @patch("app.runtime_settings.hardware_profile")
    @patch("app.runtime_settings.get_settings")
    def test_runtime_uses_recommended_model_in_automatic_mode(self, mock_get, mock_hardware):
        mock_get.return_value = {
            "model": {"chat_model": "qwen2.5:7b", "auto_select_model": True}
        }
        mock_hardware.return_value = {"recommended_model": "qwen2.5:1.5b"}

        self.assertEqual(runtime_settings()["model"]["chat_model"], "qwen2.5:1.5b")

    @patch("app.runtime_settings.hardware_profile")
    @patch("app.runtime_settings.get_settings")
    def test_runtime_keeps_manual_model(self, mock_get, mock_hardware):
        mock_get.return_value = {
            "model": {"chat_model": "qwen2.5:7b", "auto_select_model": False}
        }

        self.assertEqual(runtime_settings()["model"]["chat_model"], "qwen2.5:7b")
        mock_hardware.assert_not_called()


if __name__ == "__main__":
    unittest.main()
