"""Offline Arabic text-to-speech using a local Piper model via sherpa-onnx."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Lock
import wave

import numpy as np

try:
    from .config import PROJECT_ROOT
except ImportError:  # Support direct execution paths used by app/api.py.
    from config import PROJECT_ROOT


MODEL_NAME = "vits-piper-ar_JO-kareem-medium"
MODEL_DIR = PROJECT_ROOT / "data" / "models" / "tts" / MODEL_NAME
MODEL_FILE = MODEL_DIR / "ar_JO-kareem-medium.onnx"
TOKENS_FILE = MODEL_DIR / "tokens.txt"
ESPEAK_DATA_DIR = MODEL_DIR / "espeak-ng-data"

_engine = None
_engine_lock = Lock()


class LocalTtsUnavailable(RuntimeError):
    """Raised when the local engine or its model has not been installed."""


def model_is_ready() -> bool:
    """Return whether all files required by the local voice are present."""

    return (
        MODEL_FILE.is_file()
        and TOKENS_FILE.is_file()
        and ESPEAK_DATA_DIR.is_dir()
    )


def _load_engine():
    global _engine
    if _engine is not None:
        return _engine
    if not model_is_ready():
        raise LocalTtsUnavailable(
            f"Local Arabic voice model is missing from {MODEL_DIR}."
        )

    try:
        import sherpa_onnx
    except ImportError as error:
        raise LocalTtsUnavailable(
            "sherpa-onnx is not installed in the project environment."
        ) from error

    with _engine_lock:
        if _engine is None:
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(MODEL_FILE),
                        tokens=str(TOKENS_FILE),
                        data_dir=str(ESPEAK_DATA_DIR),
                    ),
                    num_threads=2,
                    debug=False,
                ),
                max_num_sentences=1,
            )
            if not config.validate():
                raise LocalTtsUnavailable("The local Arabic voice model is invalid.")
            _engine = sherpa_onnx.OfflineTts(config)
    return _engine


def _wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float samples as a mono 16-bit PCM WAV file."""

    normalized = np.asarray(samples, dtype=np.float32)
    pcm = (np.clip(normalized, -1.0, 1.0) * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(pcm.tobytes())
    return output.getvalue()


def synthesize_arabic(text: str, speed: float = 0.96) -> bytes:
    """Generate Modern Standard Arabic speech and return WAV bytes."""

    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise ValueError("Speech text cannot be empty.")
    if len(cleaned) > 400:
        raise ValueError("Speech text cannot exceed 400 characters per request.")
    speed = max(0.75, min(float(speed), 1.25))

    engine = _load_engine()
    with _engine_lock:
        audio = engine.generate(text=cleaned, sid=0, speed=speed)
    if audio.samples is None or len(audio.samples) == 0:
        raise RuntimeError("The local voice engine returned no audio.")
    return _wav_bytes(audio.samples, audio.sample_rate)


def voice_status() -> dict:
    """Describe the configured local voice without loading the model."""

    return {
        "available": model_is_ready(),
        "engine": "sherpa-onnx",
        "model": MODEL_NAME,
        "language": "ar",
        "voice": "Kareem",
        "offline": True,
    }
