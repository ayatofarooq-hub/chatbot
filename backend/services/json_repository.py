from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.json_storage import read_json, write_json
from app.text_encoding import repair_json_text

DATA_ROOT = PROJECT_ROOT / "data"
SEED_DATASET_ROOT = PROJECT_ROOT / "dataset"
LEGAL_PARSER_OUTPUT_ROOT = PROJECT_ROOT / "legal_document_parser" / "output" / "json"
PREFERRED_OUTPUT_ROOTS = (
    LEGAL_PARSER_OUTPUT_ROOT,
    DATA_ROOT / "output",
)
SUMMARY_ONLY_LABELS = ("الشرح التفصيلي", "الشرح التفصيلى")


class JsonRepository:
    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = data_root or DATA_ROOT
        self._document_root = self.data_root / "legal_documents"
        self._extracted_text_root = self.data_root / "extracted_text"
        self._metadata_file = self.data_root / "metadata.json"
        self._document_root.mkdir(parents=True, exist_ok=True)
        self._extracted_text_root.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path) -> dict[str, Any]:
        return repair_json_text(read_json(path, {}))

    def _save_json(self, path: Path, payload: Any) -> None:
        write_json(path, payload)

    def _iter_source_roots(self) -> tuple[Path, ...]:
        """Return the JSON roots that should be connected to the chatbot."""

        return (
            LEGAL_PARSER_OUTPUT_ROOT,
        )

    def _relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
        except ValueError:
            return str(path)

    def _is_dataset_decision_path(self, path: Path) -> bool:
        try:
            path.resolve().relative_to((SEED_DATASET_ROOT / "decisions").resolve())
            return True
        except ValueError:
            return False

    def _payload_paths(self, payload: dict[str, Any]) -> list[str]:
        paths = []
        for key in ("source_path", "source_json_path", "original_json_path", "json_path", "path"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value)
        document = payload.get("document")
        if isinstance(document, dict):
            for key in ("source_path", "source_json_path", "original_json_path", "json_path", "path"):
                value = document.get(key)
                if isinstance(value, str) and value.strip():
                    paths.append(value)
        raw_payload = payload.get("raw_payload")
        if isinstance(raw_payload, dict):
            value = raw_payload.get("source_file")
            if isinstance(value, str) and value.strip():
                paths.append(value)
        return paths

    def _is_dataset_decision_payload(self, payload: dict[str, Any]) -> bool:
        normalized_paths = [value.replace("/", "\\").lower() for value in self._payload_paths(payload)]
        return any("dataset\\decisions\\" in value for value in normalized_paths)

    def _summary_text(self, payload: dict[str, Any]) -> str:
        values = []
        for key in ("content", "text", "summary", "body", "long_text", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value)
        document = payload.get("document")
        if isinstance(document, dict):
            for key in ("content", "text", "summary", "body", "long_text", "title"):
                value = document.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value)
        return "\n".join(values)

    def _is_summary_only_dataset_decision(self, path: Path, payload: dict[str, Any]) -> bool:
        """Skip seeded decision records that are generated explanations, not sources."""

        if not self._is_dataset_decision_path(path) and not self._is_dataset_decision_payload(payload):
            return False
        text = self._summary_text(payload)
        if not any(label in text for label in SUMMARY_ONLY_LABELS):
            return False
        source_markers = (
            "قرر مجلس الوزراء",
            "قــرر مجلس الوزراء",
            "قــرّر مجلس الوزراء",
            "المنعقدة في",
            "المرقم بالعدد",
            "بناءً على",
            "بناء على",
        )
        return not any(marker in text for marker in source_markers)

    def load_json(self, path: str | Path) -> dict[str, Any]:
        return self._load_json(Path(path))

    def save_json(self, path: str | Path, payload: Any) -> None:
        self._save_json(Path(path), payload)

    def update_json(self, path: str | Path, updater: callable) -> dict[str, Any]:
        path = Path(path)
        payload = self._load_json(path)
        updated = updater(payload)
        self._save_json(path, updated)
        return updated

    def append_document(self, document: dict[str, Any]) -> dict[str, Any]:
        file_path = self._document_root / f"{document['id']}.json"
        self._save_json(file_path, document)
        return document

    def remove_document(self, document_id: str) -> None:
        for folder in (self._document_root, self._extracted_text_root):
            path = folder / f"{document_id}.json"
            if path.exists():
                path.unlink()

    def list_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for folder in self._iter_source_roots():
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*.json")):
                payload = self._load_json(path)
                if not payload:
                    continue
                if self._is_summary_only_dataset_decision(path, payload):
                    continue
                document_id = str(payload.get("id") or path.stem)
                if document_id in seen_ids:
                    continue
                seen_ids.add(document_id)
                relative_path = self._relative_path(path)
                payload.setdefault("source_json_path", relative_path)
                payload.setdefault("original_json_path", relative_path)
                documents.append(payload)
        return documents

    def find_by_id(self, document_id: str) -> dict[str, Any] | None:
        for document in self.list_documents():
            if document.get("id") == document_id:
                return document
        return None

    def find_by_title(self, title: str) -> list[dict[str, Any]]:
        needle = title.strip().lower()
        return [document for document in self.list_documents() if needle in str(document.get("title", "")).lower()]

    def find_articles(self, document_id: str) -> list[dict[str, Any]]:
        document = self.find_by_id(document_id)
        if not document:
            return []
        return document.get("articles", [])

    def search_keywords(self, keyword: str) -> list[dict[str, Any]]:
        needle = keyword.strip().lower()
        results = []
        for document in self.list_documents():
            keywords = document.get("keywords", [])
            if any(needle in str(item).lower() for item in keywords):
                results.append(document)
        return results

    def list_categories(self) -> list[str]:
        categories = set()
        for document in self.list_documents():
            for category in document.get("category", []):
                categories.add(str(category))
        return sorted(categories)

    def filter_by_document_type(self, document_type: str) -> list[dict[str, Any]]:
        return [document for document in self.list_documents() if str(document.get("document_type", "")).lower() == document_type.lower()]

    def load_metadata(self, file_name: str) -> dict[str, Any]:
        metadata = self._load_json(self._metadata_file)
        value = metadata.get(Path(file_name).stem, {})
        return value if isinstance(value, dict) else {}

    def save_metadata(self, file_name: str, payload: dict[str, Any]) -> None:
        metadata = self._load_json(self._metadata_file)
        metadata[Path(file_name).stem] = payload
        self._save_json(self._metadata_file, metadata)
