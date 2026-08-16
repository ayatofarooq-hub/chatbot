"""JSON saving component for the standalone parser pipeline."""

import json
from pathlib import Path

from config import DEFAULT_ENCODING
from exporters.filename_builder import OutputFilenameBuilder
from models.document import ParserJson
from validators.schema_validator import StandardSchemaValidator
from validators.validation_engine import ValidationEngine


class JsonExporter:
    """Save validated parser JSON to disk."""

    def __init__(self) -> None:
        self.schema_validator = StandardSchemaValidator()
        self.validation_engine = ValidationEngine()
        self.filename_builder = OutputFilenameBuilder()

    def save(self, document: ParserJson, output_dir: Path, use_source_name: bool = True) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.filename_builder.build(
            document,
            output_dir,
            use_source_name=use_source_name,
        )
        document_dict = self.schema_validator.validate_dict(document.to_dict())
        output_path.write_text(
            json.dumps(document_dict, ensure_ascii=False, indent=2),
            encoding=DEFAULT_ENCODING,
        )
        self.validation_engine.validate_file(output_path)
        return output_path
