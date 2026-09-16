"""CPU-only Arabic speech using the local Piper Kareem voice."""

from __future__ import annotations

from collections import OrderedDict
from html import unescape
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
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
ESPEAK_VOICE = os.getenv("ESPEAK_KURDISH_VOICE", "ku")
ESPEAK_EXECUTABLE = Path(
    os.getenv("ESPEAK_NG_PATH", r"C:\Program Files\eSpeak NG\espeak-ng.exe")
).expanduser()

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
    """Convert an assistant answer into concise, speakable plain text."""

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


def espeak_is_ready() -> bool:
    """Return whether the installed eSpeak-NG executable is available."""

    return ESPEAK_EXECUTABLE.is_file() or shutil.which("espeak-ng") is not None


def _espeak_executable() -> str:
    if ESPEAK_EXECUTABLE.is_file():
        return str(ESPEAK_EXECUTABLE)
    executable = shutil.which("espeak-ng")
    if executable:
        return executable
    raise LocalTtsUnavailable(
        "eSpeak-NG is not installed. Install it or set ESPEAK_NG_PATH."
    )


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

    cache_key = (f"ar:{cleaned}", round(speed_value, 3))
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


def synthesize_kurmanji(text: str, speed: float = DEFAULT_RATE) -> bytes:
    """Generate a Kurmanji Kurdish WAV locally with eSpeak-NG."""

    cleaned = normalize_arabic_for_speech(text)
    if not cleaned:
        raise ValueError("Speech text cannot be empty.")
    if len(cleaned) > MAX_CHARACTERS:
        raise ValueError(f"Speech text exceeds the {MAX_CHARACTERS} character limit.")
    if not re.search(r"[A-Za-zÇçÊêÎîŞşÛû]", cleaned):
        raise ValueError("Kurmanji speech must be written with the Latin alphabet.")
    try:
        speed_value = float(speed)
    except (TypeError, ValueError) as error:
        raise ValueError("Speech speed must be a number.") from error
    if not 0.75 <= speed_value <= 1.25:
        raise ValueError("Speech speed must be between 0.75 and 1.25.")

    cache_key = (f"ku:{cleaned}", round(speed_value, 3))
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # eSpeak's speed is expressed in words per minute. 155 is clearer than its
    # default for the Kurdish voice, while the UI multiplier remains intuitive.
    words_per_minute = max(80, min(300, round(155 * speed_value)))
    with TemporaryDirectory(prefix="mujib-espeak-") as directory:
        output_path = Path(directory) / "speech.wav"
        command = [
            _espeak_executable(),
            "-v", ESPEAK_VOICE,
            "-s", str(words_per_minute),
            "-p", "38",
            "-a", "150",
            "-w", str(output_path),
            cleaned,
        ]
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=SYNTHESIS_TIMEOUT_SECONDS,
                creationflags=creation_flags,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LocalTtsUnavailable("Could not run the local eSpeak-NG voice.") from error
        if completed.returncode != 0 or not output_path.is_file():
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "eSpeak-NG did not create a Kurdish audio file.")
        wav_content = output_path.read_bytes()

    if len(wav_content) <= 44:
        raise RuntimeError("eSpeak-NG returned an empty Kurdish audio file.")
    try:
        with wave.open(BytesIO(wav_content), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
    except (wave.Error, EOFError) as error:
        raise RuntimeError("eSpeak-NG returned an invalid Kurdish WAV file.") from error
    if not frames or not any(frames):
        raise RuntimeError("eSpeak-NG returned silent Kurdish audio. Use Latin Kurmanji text.")

    _cache_put(cache_key, wav_content)
    return wav_content


def voice_status() -> dict:
    """Describe the configured offline voice without loading it."""

    arabic_available = model_is_ready()
    kurmanji_available = espeak_is_ready()
    return {
        "available": arabic_available or kurmanji_available,
        "engine": "piper-tts + espeak-ng",
        "model": MODEL_NAME,
        "language": DEFAULT_LANGUAGE,
        "voice": "Kareem",
        "supported_languages": [
            language
            for language, available in (("ar", arabic_available), ("ku", kurmanji_available))
            if available
        ],
        "languages": {
            "ar": {
                "available": arabic_available,
                "engine": "piper-tts",
                "voice": "Kareem",
            },
            "ku": {
                "available": kurmanji_available,
                "engine": "espeak-ng",
                "voice": ESPEAK_VOICE,
                "alphabet": "Latin",
            },
        },
        "offline": True,
        "cpu_only": True,
        "max_characters": MAX_CHARACTERS,
        "default_rate": DEFAULT_RATE,
    }
