"""Index generated legal JSON chunks into the existing ChromaDB RAG store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import chromadb
from chromadb.errors import NotFoundError

from app.build_index import COLLECTION_NAME, add_chunks, create_embeddings
from app.chunk_text import CHUNKS_FILE
from app.citation_registry import save_registry
from app.config import CHROMA_FOLDER, EMBEDDING_MODEL

from .json_loader import LEGAL_JSON_OUTPUT_DIR, load_legal_json_documents
from .legal_chunker import build_chunks_from_documents


LEGAL_JSON_SOURCE_TYPE = "legal_document_parser_json"


def read_existing_chunks() -> list[dict]:
    if not CHUNKS_FILE.exists():
        return []
    chunks = []
    for line in CHUNKS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(json.loads(line))
    return chunks


def dedupe_chunks(chunks: list[dict]) -> list[dict]:
    """Keep the latest record for each chunk id while preserving order."""

    by_id: dict[str, dict] = {}
    order: list[str] = []
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
        if not chunk_id:
            continue
        if chunk_id not in by_id:
            order.append(chunk_id)
        by_id[chunk_id] = chunk
    return [by_id[chunk_id] for chunk_id in order]


def write_chunks(chunks: list[dict]) -> None:
    CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHUNKS_FILE.write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def get_or_create_collection():
    CHROMA_FOLDER.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
    try:
        return client.get_collection(COLLECTION_NAME, embedding_function=None)
    except NotFoundError:
        return client.create_collection(
            name=COLLECTION_NAME,
            metadata={
                "embedding_model": EMBEDDING_MODEL,
                "schema_version": 2,
                "primary_source_format": "json",
            },
            embedding_function=None,
        )


def remove_existing_legal_json_chunks(collection) -> None:
    try:
        existing = collection.get(where={"source_type": LEGAL_JSON_SOURCE_TYPE})
    except Exception:
        existing = {"ids": []}
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)


def index_legal_json(input_dir: Path = LEGAL_JSON_OUTPUT_DIR) -> dict:
    """Load generated legal JSON, chunk it, embed it, and save to ChromaDB."""

    documents = load_legal_json_documents(input_dir)
    if not documents:
        raise ValueError(f"No generated legal JSON files found in {input_dir}.")

    chunks = build_chunks_from_documents(documents)
    if not chunks:
        raise ValueError("Generated legal JSON files produced no chunks.")

    embeddings = create_embeddings(chunks)
    collection = get_or_create_collection()
    remove_existing_legal_json_chunks(collection)
    add_chunks(collection, chunks, embeddings)

    existing = [
        chunk
        for chunk in read_existing_chunks()
        if chunk.get("source_type") != LEGAL_JSON_SOURCE_TYPE
    ]
    all_chunks = dedupe_chunks(existing + chunks)
    write_chunks(all_chunks)
    save_registry(all_chunks)

    return {
        "input_dir": str(input_dir),
        "documents": len(documents),
        "chunks": len(chunks),
        "collection": COLLECTION_NAME,
        "collection_count": collection.count(),
        "embedding_model": EMBEDDING_MODEL,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Index generated legal JSON into the existing RAG ChromaDB store.")
    parser.add_argument("--input-dir", type=Path, default=LEGAL_JSON_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        print(json.dumps(index_legal_json(args.input_dir), ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(f"Legal JSON indexing failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
