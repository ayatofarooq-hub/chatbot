"""Configuration for the standalone parser application."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
LOG_DIR = DATA_DIR / "logs"

SUPPORTED_EXTENSIONS = {".docx", ".html", ".htm", ".md", ".pdf", ".rtf", ".txt"}
DEFAULT_ENCODING = "utf-8"
DOCUMENT_TYPE_CONFIDENCE_THRESHOLD = 0.70
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"
OLLAMA_TIMEOUT_SECONDS = 120
