from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_DOCUMENT_ROOTS = {
    "law": DATA_ROOT / "laws",
    "decision": DATA_ROOT / "decisions",
    "order": DATA_ROOT / "orders",
    "instruction": DATA_ROOT / "instructions",
    "regulation": DATA_ROOT / "regulations",
    "constitution": DATA_ROOT / "constitution",
    "amendment": DATA_ROOT / "amendments",
}
METADATA_ROOT = DATA_ROOT / "metadata"


class JsonRepository:
    def __init__(self, data_root: Path | None = None) -> None:
        self.data_root = data_root or DATA_ROOT
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_mtimes: dict[str, float] = {}
        self._lock = threading.RLock()
        self._document_roots = DEFAULT_DOCUMENT_ROOTS.copy()
        self._metadata_root = METADATA_ROOT
        self._metadata_root.mkdir(parents=True, exist_ok=True)
        for folder in self._document_roots.values():
            folder.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path) -> dict[str, Any]:
        with self._lock:
            if path.exists():
                mtime = path.stat().st_mtime
                cached = self._cache.get(str(path))
                if cached is not None and self._cache_mtimes.get(str(path)) == mtime:
                    return cached
            if not path.exists():
                return {}
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self._cache[str(path)] = payload
            self._cache_mtimes[str(path)] = path.stat().st_mtime
            return payload

    def _save_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self._cache[str(path)] = payload
        self._cache_mtimes[str(path)] = path.stat().st_mtime

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
        folder = self._document_roots.get(document.get("document_type"), self._document_roots["law"])
        file_path = folder / f"{document['id']}.json"
        self._save_json(file_path, document)
        return document

    def remove_document(self, document_id: str) -> None:
        for folder in self._document_roots.values():
            path = folder / f"{document_id}.json"
            if path.exists():
                path.unlink()

    def list_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for folder in self._document_roots.values():
            if not folder.exists():
                continue
            for path in sorted(folder.glob("*.json")):
                payload = self._load_json(path)
                if payload:
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
        metadata_path = self._metadata_root / file_name
        return self._load_json(metadata_path)

    def save_metadata(self, file_name: str, payload: dict[str, Any]) -> None:
        self._save_json(self._metadata_root / file_name, payload)
