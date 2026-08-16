"""JSON payload builders."""

from app.json_builder.document_json import build_document_json, save_document_json
from app.json_builder.legal_output import build_output_path, save_legal_json

__all__ = ["build_document_json", "save_document_json", "build_output_path", "save_legal_json"]
