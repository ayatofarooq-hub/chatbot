"""Persistent uploaded-document extraction, normalization, and indexing."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import fitz
from docx import Document

from backend.services.json_repository import JsonRepository

from .build_index import COLLECTION_NAME, add_chunks, create_embeddings
from .chunk_text import CHUNKS_FILE, build_chunks_from_document
from .citation_registry import save_registry
from .config import CHROMA_FOLDER, PROJECT_ROOT
from .json_legal_documents import document_to_loaded_document
from .text_cleaning import clean_text


UPLOAD_ROOT = PROJECT_ROOT / "data" / "legal_documents" / "uploads"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
_upload_lock = threading.RLock()


def _safe_name(name: str) -> str:
    stem = re.sub(r"[^\w\u0600-\u06ff.-]+", "_", Path(name).name)
    return stem.strip("._") or "document"


def _extract_pages(path: Path) -> list[tuple[int, str]]:
    extension = path.suffix.lower()
    if extension == ".pdf":
        with fitz.open(path) as document:
            return [
                (index + 1, clean_text(page.get_text("text")))
                for index, page in enumerate(document)
                if clean_text(page.get_text("text"))
            ]
    if extension == ".docx":
        document = Document(path)
        text = clean_text("\n".join(p.text for p in document.paragraphs))
        return [(1, text)] if text else []
    if extension == ".txt":
        text = clean_text(path.read_text(encoding="utf-8-sig"))
        return [(1, text)] if text else []
    raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _normalized_document(
    upload_id: str,
    filename: str,
    pages: list[tuple[int, str]],
) -> dict[str, Any]:
    combined = "\n\n".join(text for _, text in pages)
    first_line = next((line.strip() for line in combined.splitlines() if line.strip()), "")
    title = first_line[:240] or Path(filename).stem
    law_number = _first_match(
        r"(?:قانون|قرار|أمر)[^\n]{0,200}?\bرقم\s*(\d+)",
        combined,
    )
    year = _first_match(r"لسنة\s+(\d{4})", combined)
    return {
        "id": f"upload_{upload_id}",
        "document_type": "law",
        "category": ["uploaded"],
        "title": title,
        "law_number": law_number,
        "year": year,
        "source": f"uploaded_{upload_id}_{filename}",
        "language": "ar",
        "status": "active",
        "summary": "",
        "keywords": [],
        "upload_id": upload_id,
        "original_filename": filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "articles": [
            {
                "article_number": "",
                "page_number": page_number,
                "title": title,
                "text": text,
                "keywords": [],
                "references": [],
                "notes": "",
            }
            for page_number, text in pages
        ],
    }


def _read_chunks() -> list[dict]:
    if not CHUNKS_FILE.exists():
        return []
    return [
        json.loads(line)
        for line in CHUNKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_chunks(chunks: list[dict]) -> None:
    CHUNKS_FILE.write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def create_uploaded_document(filename: str, content: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PDF, DOCX, or TXT.")
    if not content:
        raise ValueError("The uploaded file is empty.")

    upload_id = hashlib.sha256(content).hexdigest()[:16]
    safe_filename = _safe_name(filename)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_ROOT / f"{upload_id}{extension}"

    with _upload_lock:
        repository = JsonRepository()
        existing = repository.find_by_id(f"upload_{upload_id}")
        if existing:
            return public_upload(existing, stored_path)

        stored_path.write_bytes(content)
        try:
            pages = _extract_pages(stored_path)
            if not pages:
                raise ValueError(
                    "No readable text was extracted. Scanned PDFs require OCR, which is not enabled for uploads."
                )
            document = _normalized_document(upload_id, safe_filename, pages)
            loaded = document_to_loaded_document(document)
            chunks = build_chunks_from_document(loaded)
            if not chunks:
                raise ValueError("The normalized document produced no searchable text.")
            embeddings = create_embeddings(chunks)

            repository.append_document(document)
            client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
            collection = client.get_collection(COLLECTION_NAME)
            add_chunks(collection, chunks, embeddings)
            all_chunks = _read_chunks() + chunks
            _write_chunks(all_chunks)
            save_registry(all_chunks)
            return public_upload(document, stored_path, len(chunks))
        except Exception:
            repository.remove_document(f"upload_{upload_id}")
            stored_path.unlink(missing_ok=True)
            raise


def list_uploaded_documents() -> list[dict]:
    repository = JsonRepository()
    items = []
    for document in repository.list_documents():
        upload_id = str(document.get("upload_id", ""))
        if not upload_id:
            continue
        extension = Path(str(document.get("original_filename", ""))).suffix.lower()
        items.append(
            public_upload(
                document,
                UPLOAD_ROOT / f"{upload_id}{extension}",
            )
        )
    return sorted(items, key=lambda item: item["uploaded_at"], reverse=True)


def public_upload(
    document: dict,
    stored_path: Path,
    chunk_count: int | None = None,
) -> dict:
    upload_id = str(document.get("upload_id", ""))
    if chunk_count is None:
        chunk_count = sum(
            1
            for chunk in _read_chunks()
            if str(chunk.get("document_upload_id", "")) == upload_id
        )
    return {
        "id": upload_id,
        "name": document.get("original_filename") or document.get("source"),
        "size": stored_path.stat().st_size if stored_path.exists() else 0,
        "uploaded_at": document.get("uploaded_at", ""),
        "status": "indexed",
        "title": document.get("title", ""),
        "chunk_count": chunk_count,
    }


def delete_uploaded_document(upload_id: str) -> None:
    """Remove upload-list tracking while keeping the document in the source corpus."""

    with _upload_lock:
        repository = JsonRepository()
        document = repository.find_by_id(f"upload_{upload_id}")
        if not document or str(document.get("upload_id", "")) != upload_id:
            raise LookupError("Uploaded document not found.")

        promoted = dict(document)
        promoted.pop("upload_id", None)
        promoted["source_origin"] = "uploaded"
        promoted["promoted_to_source_at"] = datetime.now(timezone.utc).isoformat()
        repository.append_document(promoted)


def uploaded_file_path(upload_id: str) -> tuple[Path, str]:
    repository = JsonRepository()
    document = repository.find_by_id(f"upload_{upload_id}")
    if not document or str(document.get("upload_id", "")) != upload_id:
        raise LookupError("Uploaded document not found.")
    filename = str(document.get("original_filename") or "document")
    path = UPLOAD_ROOT / f"{upload_id}{Path(filename).suffix.lower()}"
    if not path.exists():
        raise LookupError("Uploaded file not found.")
    return path, filename
