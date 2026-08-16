"""Bridge the independent legal_document_parser into the chatbot index."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_legal_parser_docx_files(files: list[Path] | None = None) -> list[dict[str, Any]]:
    """Parse parser-owned DOCX files into legal_document_parser/output/json."""

    from legal_document_parser.main import list_input_files, metrics, parse_file

    input_files = files if files is not None else list_input_files()
    results: list[dict[str, Any]] = []
    for input_path in input_files:
        output_path, payload, errors = parse_file(input_path)
        results.append(metrics(input_path, output_path, payload, errors))
    return results


def index_legal_parser_json_outputs(input_dir: Path | None = None) -> dict[str, Any]:
    """Index generated legal_document_parser JSON files into the chatbot RAG store."""

    from legal_rag.index_legal_json import index_legal_json
    from legal_rag.json_loader import LEGAL_JSON_OUTPUT_DIR

    return index_legal_json(input_dir or LEGAL_JSON_OUTPUT_DIR)


def rebuild_legal_parser_index(*, parse_docx: bool = True) -> dict[str, Any]:
    """Parse legal DOCX files, then index their generated JSON into app search."""

    parse_results = parse_legal_parser_docx_files() if parse_docx else []
    index_result = index_legal_parser_json_outputs()
    return {
        "parsed_documents": len(parse_results),
        "parser_validation_errors": sum(
            len(item.get("validation_errors") or []) for item in parse_results
        ),
        "parser_outputs": parse_results,
        "index": index_result,
    }
