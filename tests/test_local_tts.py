"""Tests for CPU-only Piper Arabic speech normalization and caching."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import app.local_tts as local_tts


class _FakeVoice:
    def __init__(self):
        self.calls = 0

    def synthesize_wav(self, text, wav_file, syn_config=None):
        self.calls += 1
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 64)


class LocalTtsTests(unittest.TestCase):
    def setUp(self):
        local_tts.clear_tts_cache()

    def test_normalizes_arabic_markdown_urls_and_punctuation(self):
        text = "# **مرحباً**; راجع [القانون](https://example.com)؟؟"

        normalized = local_tts.normalize_arabic_for_speech(text)

        self.assertEqual(normalized, "مرحباً؛ راجع القانون؟")

    def test_code_blocks_are_not_read_verbatim(self):
        normalized = local_tts.normalize_arabic_for_speech(
            "النتيجة: ```python\nprint('secret')\n```"
        )

        self.assertNotIn("print", normalized)
        self.assertIn("مقطعاً برمجياً", normalized)

    def test_mixed_arabic_numbers_dates_and_english_are_preserved(self):
        value = "صدر القرار رقم ١٢٣ بتاريخ 2026/09/01 باستخدام FastAPI."

        self.assertEqual(local_tts.normalize_arabic_for_speech(value), value)

    def test_missing_model_or_config_is_reported(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with (
                patch.object(local_tts, "MODEL_FILE", missing.with_suffix(".onnx")),
                patch.object(local_tts, "CONFIG_FILE", missing.with_suffix(".json")),
            ):
                self.assertFalse(local_tts.model_is_ready())

    def test_rejects_empty_and_overlong_text(self):
        with self.assertRaises(ValueError):
            local_tts.synthesize_arabic("   ")
        with patch.object(local_tts, "MAX_CHARACTERS", 5):
            with self.assertRaises(ValueError):
                local_tts.synthesize_arabic("نص طويل جداً")

    def test_rejects_invalid_rate(self):
        with self.assertRaises(ValueError):
            local_tts.synthesize_arabic("مرحباً", 1.5)

    def test_identical_requests_use_bounded_memory_cache(self):
        voice = _FakeVoice()
        with patch.object(local_tts, "_load_voice", return_value=voice):
            first = local_tts.synthesize_arabic("مرحباً بك", 1.0)
            second = local_tts.synthesize_arabic("مرحباً بك", 1.0)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith(b"RIFF"))
        self.assertEqual(voice.calls, 1)

    def test_kurmanji_rejects_non_latin_text_before_running_engine(self):
        with self.assertRaisesRegex(ValueError, "Latin alphabet"):
            local_tts.synthesize_kurmanji("سڵاو")

    def test_voice_status_reports_each_offline_language(self):
        with (
            patch.object(local_tts, "model_is_ready", return_value=True),
            patch.object(local_tts, "espeak_is_ready", return_value=True),
        ):
            status = local_tts.voice_status()

        self.assertTrue(status["languages"]["ar"]["available"])
        self.assertTrue(status["languages"]["ku"]["available"])
        self.assertEqual(status["languages"]["ku"]["engine"], "espeak-ng")


if __name__ == "__main__":
    unittest.main()
