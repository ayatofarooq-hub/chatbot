"""Manage source text documents and their corresponding Chroma records."""

import threading
from pathlib import Path

import chromadb

try:
    from .build_index import COLLECTION_NAME, add_chunks, create_embeddings
    from .chunk_text import build_chunks_from_content
    from .config import CHROMA_FOLDER, EXTRACTED_TEXT_FOLDER
except ImportError:
    from build_index import COLLECTION_NAME, add_chunks, create_embeddings
    from chunk_text import build_chunks_from_content
    from config import CHROMA_FOLDER, EXTRACTED_TEXT_FOLDER


WRITE_LOCK = threading.Lock()


def normalize_filename(filename: str) -> str:
    """Validate and normalize one managed text-document filename."""

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Field 'filename' must be a non-empty string.")

    filename = filename.strip()
    if Path(filename).name != filename or filename in {".", "..", ".gitkeep"}:
        raise ValueError("Filename must not contain a directory path.")
    if not filename.lower().endswith(".txt"):
        filename += ".txt"
    return filename


def document_path(filename: str) -> Path:
    """Return a validated path inside the extracted-text directory."""

    path = (EXTRACTED_TEXT_FOLDER / normalize_filename(filename)).resolve()
    if path.parent != EXTRACTED_TEXT_FOLDER.resolve():
        raise ValueError("Invalid document path.")
    return path


def list_documents() -> list[dict]:
    """List managed source text documents."""

    EXTRACTED_TEXT_FOLDER.mkdir(parents=True, exist_ok=True)
    return [
        {"filename": path.name, "size_bytes": path.stat().st_size}
        for path in sorted(EXTRACTED_TEXT_FOLDER.glob("*.txt"))
        if path.is_file()
    ]


def get_collection():
    """Open the existing Chroma collection used by the chatbot."""

    client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )


def prepare_document(filename: str, content: str) -> tuple[str, str, list, list]:
    """Create validated chunks and embeddings before changing stored data."""

    filename = normalize_filename(filename)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Field 'content' must be a non-empty string.")

    stored_content = content
    if "--- PAGE " not in content:
        stored_content = f"--- PAGE 1 ---\n{content.strip()}\n"

    chunks = build_chunks_from_content(filename, stored_content)
    if not chunks:
        raise ValueError("Document content did not produce any indexable chunks.")

    embeddings = create_embeddings(chunks)
    return filename, stored_content, chunks, embeddings


def insert_document(filename: str, content: str) -> dict:
    """Create a source document and insert its chunks into Chroma."""

    filename, stored_content, chunks, embeddings = prepare_document(
        filename,
        content,
    )
    path = document_path(filename)

    with WRITE_LOCK:
        if path.exists():
            raise FileExistsError(filename)
        collection = get_collection()
        add_chunks(collection, chunks, embeddings)
        path.write_text(stored_content, encoding="utf-8")

    return {"filename": filename, "chunk_count": len(chunks)}


def update_document(filename: str, content: str) -> dict:
    """Replace one source document and all of its indexed chunks."""

    filename, stored_content, chunks, embeddings = prepare_document(
        filename,
        content,
    )
    path = document_path(filename)

    with WRITE_LOCK:
        if not path.exists():
            raise FileNotFoundError(filename)
        collection = get_collection()
        collection.delete(where={"source_file": filename})
        add_chunks(collection, chunks, embeddings)
        path.write_text(stored_content, encoding="utf-8")

    return {"filename": filename, "chunk_count": len(chunks)}


def delete_document(filename: str) -> dict:
    """Delete one source document and all of its indexed chunks."""

    filename = normalize_filename(filename)
    path = document_path(filename)

    with WRITE_LOCK:
        if not path.exists():
            raise FileNotFoundError(filename)
        collection = get_collection()
        collection.delete(where={"source_file": filename})
        path.unlink()

    return {"filename": filename, "deleted": True}
