"""Command-line entry point for the standalone parser application."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable, TypeVar

from builders.document_builder import JsonBuilder
from cleaners.text_cleaner import DocumentCleaner
from config import INPUT_DIR, OUTPUT_DIR, SUPPORTED_EXTENSIONS
from detectors.iraqi_government_detector import IraqiGovernmentDocumentDetector
from exporters.json_exporter import JsonExporter
from extractors.basic_metadata import MetadataExtractor
from extractors.legal_extraction_engine import LegalExtractionEngine
from extractors.qwen_legal_analyzer import QwenLegalAnalyzer
from loaders.document_loader import DocumentLoader
from utils.filesystem import ensure_directories, iter_input_files
from utils.logging import (
    get_parser_logger,
    log_stage_complete,
    log_stage_error,
    log_stage_start,
)
from validators.document_validator import JsonValidator
from validators.validation_engine import ValidationError


T = TypeVar("T")


class ParserPipeline:
    """Independent parser execution flow."""

    def __init__(
        self,
        use_llm: bool = False,
        include_summary: bool = True,
        use_source_filenames: bool = True,
    ) -> None:
        self.use_llm = use_llm
        self.include_summary = include_summary
        self.use_source_filenames = use_source_filenames
        self.loader = DocumentLoader()
        self.cleaner = DocumentCleaner()
        self.document_detector = IraqiGovernmentDocumentDetector()
        self.metadata_extractor = MetadataExtractor()
        self.legal_extraction_engine = LegalExtractionEngine()
        self.legal_analyzer = QwenLegalAnalyzer() if use_llm else None
        self.builder = JsonBuilder()
        self.validator = JsonValidator()
        self.exporter = JsonExporter()
        self.logger = get_parser_logger()

    def process(self, source_path: Path, output_dir: Path) -> Path | None:
        filename = source_path.name
        try:
            return self._process_once(source_path, output_dir)
        except ValidationError as first_error:
            try:
                return self._process_once(source_path, output_dir)
            except ValidationError as retry_error:
                self.logger.error(
                    "[%s] Validating JSON failed after retry: first=%s retry=%s",
                    filename,
                    first_error,
                    retry_error,
                )
                return None
        except Exception as error:
            self.logger.exception("[%s] Processing failed: %s", filename, error)
            return None

    def _process_once(self, source_path: Path, output_dir: Path) -> Path:
        filename = source_path.name
        loaded_document = self._run_stage(
            filename,
            "Loading document",
            lambda: self.loader.load(source_path),
        )
        cleaned_document = self._run_stage(
            filename,
            "Cleaning document",
            lambda: self.cleaner.clean(loaded_document),
        )
        document_type = self._run_stage(
            filename,
            "Detecting document type",
            lambda: self.document_detector.detect(cleaned_document),
        )
        metadata = self._run_stage(
            filename,
            "Extracting metadata",
            lambda: self.metadata_extractor.extract(cleaned_document),
        )
        legal_content = self._run_stage(
            filename,
            "Extracting legal content",
            lambda: self.legal_extraction_engine.extract(
                cleaned_document,
                metadata,
                document_type,
                original_body=loaded_document.raw_text,
                original_paragraphs=loaded_document.paragraphs,
            ),
        )
        llm_analysis = None
        if self.legal_analyzer is not None:
            missing_fields = self.legal_extraction_engine.missing_llm_fields(legal_content)
            if missing_fields:
                llm_analysis = self._run_stage(
                    filename,
                    "Running Qwen",
                    lambda: self.legal_analyzer.analyze(
                        cleaned_document,
                        metadata,
                        document_type,
                        include_summary=self.include_summary,
                        requested_fields=missing_fields,
                    ),
                )
                legal_content = self._run_stage(
                    filename,
                    "Merging Qwen output",
                    lambda: self.legal_extraction_engine.extract(
                        cleaned_document,
                        metadata,
                        document_type,
                        llm_analysis=llm_analysis,
                        original_body=loaded_document.raw_text,
                        original_paragraphs=loaded_document.paragraphs,
                    ),
                )
        elif legal_content.body != loaded_document.raw_text:
            legal_content = replace(legal_content, body=loaded_document.raw_text)
        parser_json = self._run_stage(
            filename,
            "Building JSON",
            lambda: self.builder.build(metadata, document_type, legal_content, llm_analysis),
        )
        validated_json = self._run_stage(
            filename,
            "Validating JSON",
            lambda: self.validator.validate(parser_json),
        )
        output_path = self._run_stage(
            filename,
            "Saving output",
            lambda: self.exporter.save(
                validated_json,
                output_dir,
                use_source_name=self.use_source_filenames,
            ),
        )
        self.logger.info("[%s] Completed. Output: %s", filename, output_path)
        return output_path

    def _run_stage(self, filename: str, stage: str, action: Callable[[], T]) -> T:
        log_stage_start(self.logger, filename, stage)
        try:
            result = action()
        except Exception as error:
            log_stage_error(self.logger, filename, stage, error)
            raise
        log_stage_complete(self.logger, filename, stage)
        return result


def run(
    input_dir: Path = INPUT_DIR,
    output_dir: Path = OUTPUT_DIR,
    use_llm: bool = False,
    include_summary: bool = True,
    use_source_filenames: bool = True,
) -> list[Path]:
    return run_paths(
        [input_dir],
        output_dir=output_dir,
        use_llm=use_llm,
        include_summary=include_summary,
        use_source_filenames=use_source_filenames,
    )


def run_paths(
    input_paths: list[Path],
    output_dir: Path = OUTPUT_DIR,
    use_llm: bool = False,
    include_summary: bool = True,
    use_source_filenames: bool = True,
) -> list[Path]:
    ensure_directories(output_dir)
    outputs: list[Path] = []
    pipeline = ParserPipeline(
        use_llm=use_llm,
        include_summary=include_summary,
        use_source_filenames=use_source_filenames,
    )

    for source_path in collect_source_files(input_paths):
        output_path = pipeline.process(source_path, output_dir)
        if output_path is not None:
            outputs.append(output_path)

    return outputs


def collect_source_files(input_paths: list[Path]) -> list[Path]:
    logger = get_parser_logger()
    source_files: list[Path] = []
    for input_path in input_paths:
        if input_path.is_dir():
            source_files.extend(iter_input_files(input_path, SUPPORTED_EXTENSIONS))
        elif input_path.is_file():
            if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                logger.error("Skipping unsupported input file: %s", input_path)
                continue
            source_files.append(input_path)
        else:
            logger.error("Skipping missing input path: %s", input_path)

    return sorted(source_files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse documents into standalone JSON output.")
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Optional file or directory paths to process, e.g. python main.py input/document.docx",
    )
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable parser-only Qwen2.5-1.5B analysis through local Ollama.",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Disable LLM summary generation while keeping other structured LLM fields.",
    )
    parser.add_argument(
        "--legal-filenames",
        action="store_true",
        help="Use legal-derived names like decision_2024_245.json instead of source stems.",
    )
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    input_paths = args.inputs or [args.input_dir]
    outputs = run_paths(
        input_paths,
        args.output_dir,
        use_llm=args.use_llm,
        include_summary=not args.no_summary,
        use_source_filenames=not args.legal_filenames,
    )

    if not outputs:
        print(
            "No supported input files found. "
            f"Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}"
        )
        return 0

    for output_path in outputs:
        print(f"Wrote {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
