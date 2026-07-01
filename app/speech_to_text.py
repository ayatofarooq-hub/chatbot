"""Offline Arabic speech-to-text using a lazily loaded Whisper model."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np

DEFAULT_MODEL = "small"
_model = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError(
                "Speech transcription is not installed. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from error

        model_name = os.getenv("WHISPER_MODEL", DEFAULT_MODEL)
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv(
            "WHISPER_COMPUTE_TYPE",
            "int8" if device == "cpu" else "float16",
        )
        _model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )
        return _model


def transcribe_audio(audio_path: str | Path) -> str:
    """Transcribe one audio file as Arabic and return normalized text."""

    model = _load_model()
    segments, _ = model.transcribe(
        str(audio_path),
        language="ar",
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        segments, _ = model.transcribe(
            str(audio_path),
            language="ar",
            vad_filter=False,
            beam_size=5,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise ValueError(
            "لم يتم اكتشاف كلام واضح. تحدث بالقرب من الميكروفون لمدة ثانيتين على الأقل."
        )
    return text


def inspect_audio(audio_path: str | Path) -> dict[str, float | int]:
    """Measure decoded audio without retaining the recording."""

    try:
        import av

        sample_count = 0
        square_sum = 0.0
        peak = 0.0
        sample_rate = 0
        channel_count = 1
        with av.open(str(audio_path)) as container:
            stream = container.streams.audio[0]
            for packet in container.demux(stream):
                for frame in packet.decode():
                    samples = frame.to_ndarray()
                    if np.issubdtype(samples.dtype, np.integer):
                        scale = float(max(abs(np.iinfo(samples.dtype).min), np.iinfo(samples.dtype).max))
                        samples = samples.astype(np.float32) / scale
                    else:
                        samples = samples.astype(np.float32, copy=False)
                    sample_count += samples.size
                    square_sum += float(np.square(samples, dtype=np.float64).sum())
                    peak = max(peak, float(np.abs(samples).max(initial=0.0)))
                    sample_rate = frame.sample_rate or sample_rate
                    channel_count = max(1, samples.shape[0])
        duration = (
            sample_count / (sample_rate * channel_count) if sample_rate else 0.0
        )
        rms = (square_sum / sample_count) ** 0.5 if sample_count else 0.0
        return {
            "duration_seconds": round(duration, 2),
            "sample_count": sample_count,
            "rms": round(rms, 6),
            "peak": round(peak, 6),
        }
    except Exception:
        return {
            "duration_seconds": 0.0,
            "sample_count": 0,
            "rms": 0.0,
            "peak": 0.0,
        }
