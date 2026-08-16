"""Build independent output JSON filenames."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from models.document import ParserJson


_TYPE_PREFIXES = {
    "Cabinet Decision": "decision",
    "Law": "law",
    "Regulation": "regulation",
    "Cabinet Recommendation": "cabinet_recommendation",
    "Ministerial Order": "ministerial_order",
    "Official Letter": "official_letter",
    "Circular": "circular",
    "Instruction": "instruction",
    "Council Resolution": "council_resolution",
    "Unknown": "document",
}
_DATE_PATTERN = re.compile(r"([\d\u0660-\u0669]{4})")
_NUMBER_PATTERN = re.compile(r"[\d\u0660-\u0669]+")


class OutputFilenameBuilder:
    """Create stable parser_app output names without using chatbot data."""

    def build(self, document: ParserJson, output_dir: Path, use_source_name: bool = True) -> Path:
        if use_source_name:
            filename = f"{self._safe_stem(document.metadata.stem)}.json"
            return self._deduplicate(output_dir / filename)

        prefix = _TYPE_PREFIXES.get(document.document_type.document_type, "document")
        year = self._year(document) or "unknown_year"
        number = self._number(document) or self._stable_suffix(document)
        filename = f"{prefix}_{year}_{number}.json"
        return self._deduplicate(output_dir / filename)

    def _year(self, document: ParserJson) -> str | None:
        for value in (
            document.metadata.issue_date,
            document.metadata.session_date,
            document.created_at,
        ):
            if not value:
                continue
            normalized = self._arabic_digits_to_ascii(value)
            matches = _DATE_PATTERN.findall(normalized)
            if matches:
                return matches[-1]
        return None

    def _number(self, document: ParserJson) -> str | None:
        for value in (
            document.metadata.document_number,
            document.metadata.reference_number,
        ):
            if not value:
                continue
            matches = _NUMBER_PATTERN.findall(self._arabic_digits_to_ascii(value))
            if matches:
                return "_".join(matches)
        return None

    def _stable_suffix(self, document: ParserJson) -> str:
        value = "|".join(
            item or ""
            for item in (
                document.metadata.source_name,
                document.metadata.subject,
                document.legal_content.title,
            )
        )
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]

    def _deduplicate(self, output_path: Path) -> Path:
        if not output_path.exists():
            return output_path

        stem = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent
        counter = 2
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _safe_stem(self, value: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
        return cleaned or "document"

    def _arabic_digits_to_ascii(self, value: str) -> str:
        return value.translate(
            str.maketrans("\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669", "0123456789")
        )
