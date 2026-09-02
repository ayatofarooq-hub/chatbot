"""CPU-only Arabic speech using the local Piper Kareem voice."""

from __future__ import annotations

from collections import OrderedDict
from html import unescape
from io import BytesIO
import os
from pathlib import Path
import re
from threading import Lock
import wave

from dotenv import load_dotenv

try:
    from .config import PROJECT_ROOT
except ImportError:  # Support direct execution paths used by app/api.py.
    from config import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env", override=False)

MODEL_NAME = "ar_JO-kareem-medium"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "data" / "models" / "tts" / f"vits-piper-{MODEL_NAME}"
MODEL_FILE = Path(os.getenv("PIPER_MODEL_PATH", str(DEFAULT_MODEL_DIR / f"{MODEL_NAME}.onnx"))).expanduser()
CONFIG_FILE = Path(os.getenv("PIPER_CONFIG_PATH", str(DEFAULT_MODEL_DIR / f"{MODEL_NAME}.onnx.json"))).expanduser()
DEFAULT_LANGUAGE = os.getenv("TTS_DEFAULT_LANGUAGE", "ar")
DEFAULT_RATE = float(os.getenv("TTS_DEFAULT_RATE", "1.0"))
MAX_CHARACTERS = max(1, int(os.getenv("TTS_MAX_CHARACTERS", "2000")))
CACHE_SIZE = max(1, int(os.getenv("TTS_CACHE_SIZE", "24")))
SYNTHESIS_TIMEOUT_SECONDS = max(5.0, float(os.getenv("TTS_TIMEOUT_SECONDS", "60")))

_voice = None
_voice_lock = Lock()
_cache_lock = Lock()
_audio_cache: OrderedDict[tuple[str, float], bytes] = OrderedDict()


class LocalTtsUnavailable(RuntimeError):
    """Raised when Piper or the configured local voice is unavailable."""


_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\s)]+(?:\s+['\"][^'\"]*['\"])?\)")
_BARE_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_CITATION_RE = re.compile(r"\[(?:\d+(?:\s*[-،,]\s*\d+)*|مصدر[^\]]*)\]")
_MARKDOWN_RE = re.compile(r"(?m)^\s{0,3}(?:#{1,6}|>|[-+*]\s|\d+[.)]\s)\s*")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_arabic_for_speech(value: str) -> str:
    """Convert an assistant answer into concise, speakable UTF-8 Arabic text."""

    text = unescape(str(value or "")).replace("\u200f", " ").replace("\u200e", " ")
    had_code = bool(_CODE_BLOCK_RE.search(text))
    text = _CODE_BLOCK_RE.sub(" ", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = _BARE_URL_RE.sub(" رابط إلكتروني ", text)
    text = _CITATION_RE.sub(" ", text)
    text = _HTML_RE.sub(" ", text)
    text = _MARKDOWN_RE.sub("", text)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = text.replace(";", "؛").replace("?", "؟").replace("…", ".")
    text = re.sub(r"([!؟،؛.])\1+", r"\1", text)
    text = _WHITESPACE_RE.sub(" ", text).strip(" -\n\t")
    if had_code:
        notice = "تتضمن الإجابة مقطعاً برمجياً لم تتم قراءته."
        text = f"{text} {notice}".strip()
    return text


def model_is_ready() -> bool:
    """Return whether the configured Piper ONNX model and JSON config exist."""

    return MODEL_FILE.is_file() and CONFIG_FILE.is_file()


def _load_voice():
    global _voice
    if _voice is not None:
        return _voice
    if not model_is_ready():
        raise LocalTtsUnavailable(
            "ملفات صوت Kareem المحلي غير موجودة. تحقق من PIPER_MODEL_PATH وPIPER_CONFIG_PATH."
        )
    try:
        from piper import PiperVoice
    except ImportError as error:
        raise LocalTtsUnavailable(
            "حزمة piper-tts غير مثبتة في البيئة الافتراضية للمشروع."
        ) from error

    with _voice_lock:
        if _voice is None:
            try:
                _voice = PiperVoice.load(
                    MODEL_FILE,
                    config_path=CONFIG_FILE,
                    use_cuda=False,
                )
            except Exception as error:
                raise LocalTtsUnavailable(
                    "تعذر تحميل نموذج Kareem المحلي. تحقق من توافق ملفي ONNX وJSON."
                ) from error
    return _voice


def _cache_get(key: tuple[str, float]) -> bytes | None:
    with _cache_lock:
        value = _audio_cache.get(key)
        if value is not None:
            _audio_cache.move_to_end(key)
        return value


def _cache_put(key: tuple[str, float], value: bytes) -> None:
    with _cache_lock:
        _audio_cache[key] = value
        _audio_cache.move_to_end(key)
        while len(_audio_cache) > CACHE_SIZE:
            _audio_cache.popitem(last=False)


def clear_tts_cache() -> None:
    """Clear generated audio; useful for tests and explicit maintenance."""

    with _cache_lock:
        _audio_cache.clear()


def synthesize_arabic(text: str, speed: float = DEFAULT_RATE) -> bytes:
    """Generate a complete mono WAV in memory with Piper on CPU."""

    cleaned = normalize_arabic_for_speech(text)
    if not cleaned:
        raise ValueError("نص النطق لا يمكن أن يكون فارغاً.")
    if len(cleaned) > MAX_CHARACTERS:
        raise ValueError(f"نص النطق يتجاوز الحد الأقصى البالغ {MAX_CHARACTERS} حرفاً.")
    try:
        speed_value = float(speed)
    except (TypeError, ValueError) as error:
        raise ValueError("سرعة النطق يجب أن تكون رقماً.") from error
    if not 0.75 <= speed_value <= 1.25:
        raise ValueError("سرعة النطق يجب أن تكون بين 0.75 و1.25.")

    cache_key = (cleaned, round(speed_value, 3))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    voice = _load_voice()
    try:
        from piper import SynthesisConfig
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            with _voice_lock:
                voice.synthesize_wav(
                    cleaned,
                    wav_file,
                    syn_config=SynthesisConfig(
                        length_scale=1.0 / speed_value,
                        normalize_audio=True,
                    ),
                )
        wav_content = output.getvalue()
    except Exception as error:
        raise RuntimeError("تعذر إنشاء الصوت العربي المحلي.") from error
    if len(wav_content) <= 44:
        raise RuntimeError("أعاد محرك الصوت ملفاً صوتياً فارغاً.")
    _cache_put(cache_key, wav_content)
    return wav_content


def voice_status() -> dict:
    """Describe the configured offline voice without loading it."""

    return {
        "available": model_is_ready(),
        "engine": "piper-tts",
        "model": MODEL_NAME,
        "language": DEFAULT_LANGUAGE,
        "voice": "Kareem",
        "offline": True,
        "cpu_only": True,
        "max_characters": MAX_CHARACTERS,
        "default_rate": DEFAULT_RATE,
    }
