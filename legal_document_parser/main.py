"""Run the independent DOCX to JSON legal document parser."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .config import INPUT_DOCX_DIR, OUTPUT_JSON_DIR, SCHEMA_PATH, ensure_directories
    from .parser.docx_parser import DocxParser
    from .parser.json_builder import LegalJsonBuilder, validate_payload
except ImportError:
    from config import INPUT_DOCX_DIR, OUTPUT_JSON_DIR, SCHEMA_PATH, ensure_directories
    from parser.docx_parser import DocxParser
    from parser.json_builder import LegalJsonBuilder, validate_payload


def list_input_files() -> list[Path]:
    """Return DOCX files from the parser-owned input directory."""

    return sorted(INPUT_DOCX_DIR.glob("*.docx"))


def parse_file(path: Path) -> tuple[Path, dict[str, Any], list[str]]:
    """Parse one DOCX and write one UTF-8 JSON file."""

    parsed = DocxParser().parse(path)
    payload = LegalJsonBuilder().build(parsed)
    validation_errors = validate_payload(payload, SCHEMA_PATH)
    output_path = OUTPUT_JSON_DIR / f"{path.stem}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path, payload, validation_errors


def metrics(input_path: Path, output_path: Path, payload: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Build required processing metrics."""

    return {
        "input_file": str(input_path),
        "generated_json_file": str(output_path),
        "paragraph_count": len(payload.get("paragraphs", [])),
        "section_count": len(payload.get("decision", {}).get("sections", [])),
        "legal_item_count": len(payload.get("decision", {}).get("numbered_items", [])),
        "body_length": len(payload.get("body", "")),
        "long_text_length": len(payload.get("long_text", "")),
        "validation_result": "valid" if not errors else "invalid",
        "validation_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert parser-owned DOCX files to standalone legal JSON.")
    parser.add_argument("files", nargs="*", type=Path, help="Optional DOCX files to parse instead of input/docx.")
    args = parser.parse_args()

    ensure_directories()
    files = args.files or list_input_files()
    if not files:
        print(f"No DOCX files found in {INPUT_DOCX_DIR}")
        return 1

    exit_code = 0
    for input_path in files:
        try:
            output_path, payload, errors = parse_file(input_path)
            if errors:
                exit_code = 1
            print(json.dumps(metrics(input_path, output_path, payload, errors), ensure_ascii=False, indent=2))
        except Exception as error:
            exit_code = 1
            print(f"Failed to parse {input_path}: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
