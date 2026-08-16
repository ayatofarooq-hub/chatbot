"""Configuration for the independent legal document parser."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_DOCX_DIR = BASE_DIR / "input" / "docx"
OUTPUT_JSON_DIR = BASE_DIR / "output" / "json"
SCHEMA_PATH = BASE_DIR / "schemas" / "legal_document_v2.json"
DEFAULT_ENCODING = "utf-8"
SUPPORTED_EXTENSION = ".docx"


def ensure_directories() -> None:
    """Create parser-owned input and output directories."""

    INPUT_DOCX_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)

