"""Tests for the offline speech transcription wrapper."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.speech_to_text import transcribe_audio


class SpeechToTextTests(unittest.TestCase):
    @patch("app.speech_to_text._load_model")
    def test_retries_without_vad_when_first_pass_is_empty(self, load_model):
        model = Mock()
        model.transcribe.side_effect = [
            ([], None),
            ([SimpleNamespace(text="  سؤال قانوني  ")], None),
        ]
        load_model.return_value = model

        self.assertEqual(transcribe_audio("recording.webm"), "سؤال قانوني")
        self.assertTrue(model.transcribe.call_args_list[0].kwargs["vad_filter"])
        self.assertFalse(model.transcribe.call_args_list[1].kwargs["vad_filter"])

    @patch("app.speech_to_text._load_model")
    def test_reports_arabic_error_when_both_passes_are_empty(self, load_model):
        model = Mock()
        model.transcribe.return_value = ([], None)
        load_model.return_value = model

        with self.assertRaisesRegex(ValueError, "لم يتم اكتشاف كلام واضح"):
            transcribe_audio("recording.webm")


if __name__ == "__main__":
    unittest.main()
