from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document

from .json_repository import JsonRepository


class DocumentService:
    def __init__(self, repository: JsonRepository | None = None) -> None:
        self.repository = repository or JsonRepository()

    def convert_docx_to_json(self, source_path: str | Path) -> dict[str, Any]:
        document = Document(source_path)
        blocks = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                blocks.append(text)
        title = blocks[0] if blocks else Path(source_path).stem
        payload = {
            "id": self._slugify(title),
            "document_type": "law",
            "category": "general",
            "title": title,
            "law_number": "",
            "year": "",
            "source": str(source_path),
            "publication_date": "",
            "language": "ar",
            "status": "active",
            "summary": "",
            "keywords": [],
            "articles": [
                {
                    "article_number": "1",
                    "title": title,
                    "text": "\n".join(blocks),
                    "keywords": [],
                    "references": [],
                    "notes": "",
                }
            ],
        }
        self.repository.append_document(payload)
        return payload

    def import_directory(self, directory: str | Path) -> list[dict[str, Any]]:
        folder = Path(directory)
        documents = []
        for path in sorted(folder.glob("*.docx")):
            documents.append(self.convert_docx_to_json(path))
        return documents

    def _slugify(self, value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in value)
        cleaned = "_".join(part for part in cleaned.split("_") if part)
        return cleaned.lower() or "document"
