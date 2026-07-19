from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT
from app.json_storage import read_json, write_json
from app.text_encoding import repair_json_text

DATA_ROOT = PROJECT_ROOT / "data"
SEED_DATASET_ROOT = PROJECT_ROOT / "dataset"


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
        for folder in (self._document_root, self._extracted_text_root, SEED_DATASET_ROOT):
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*.json")):
                payload = self._load_json(path)
                if not payload:
                    continue
                document_id = str(payload.get("id") or path.stem)
                if document_id in seen_ids:
                    continue
                seen_ids.add(document_id)
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
