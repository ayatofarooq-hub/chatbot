from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError
from tqdm import tqdm

from app.config import CHROMA_FOLDER, EMBEDDING_MODEL, OLLAMA_KEEP_ALIVE, OLLAMA_REQUEST_TIMEOUT_SECONDS
from app.runtime_settings import runtime_settings
from .json_repository import JsonRepository

COLLECTION_NAME = "iraqi_legal_documents"
EMBEDDING_BATCH_SIZE = 16
CHROMA_BATCH_SIZE = 100
CHUNKS_FILE = Path(__file__).resolve().parents[2] / "data" / "chunks.jsonl"


class EmbeddingService:
    def __init__(self, repository: JsonRepository | None = None) -> None:
        self.repository = repository or JsonRepository()

    def build_chunks(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for document in self.repository.list_documents():
            for article in document.get("articles", []):
                text = article.get("text") or ""
                if not text.strip():
                    continue
                chunk_id = self._chunk_id(document["id"], article.get("article_number", "1"))
                chunks.append({
                    "id": chunk_id,
                    "source_file": document.get("source", document["id"]),
                    "document_type": document.get("document_type", "law"),
                    "document_title": document.get("title", ""),
                    "article_reference": article.get("article_number", ""),
                    "text": text,
                    "document_id": document.get("id"),
                })
        return chunks

    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        CHUNKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CHUNKS_FILE.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    def create_embeddings(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        settings = runtime_settings()["model"]
        active_client = ollama.Client(host=settings["ollama_base_url"], timeout=settings["request_timeout"])
        embeddings = []
        for start in tqdm(range(0, len(chunks), EMBEDDING_BATCH_SIZE), desc="Generating embeddings", unit="batch"):
            batch = chunks[start:start + EMBEDDING_BATCH_SIZE]
            response = active_client.embed(
                model=settings["embedding_model"],
                input=[chunk["text"] for chunk in batch],
                keep_alive=settings["keep_alive"],
            )
            batch_embeddings = response["embeddings"]
            if len(batch_embeddings) != len(batch):
                raise RuntimeError("Ollama returned a different number of embeddings than requested.")
            embeddings.extend(batch_embeddings)
        return embeddings

    def rebuild(self) -> int:
        chunks = self.build_chunks()
        if not chunks:
            raise ValueError("No JSON legal records were found to index.")
        self.save_chunks(chunks)
        embeddings = self.create_embeddings(chunks)
        CHROMA_FOLDER.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
        collection = self._reset_collection(client)
        self._add_chunks(collection, chunks, embeddings)
        return collection.count()

    def _reset_collection(self, client) -> Any:
        try:
            client.delete_collection(COLLECTION_NAME)
        except NotFoundError:
            pass
        return client.create_collection(name=COLLECTION_NAME, metadata={"embedding_model": EMBEDDING_MODEL, "schema_version": 2, "primary_source_format": "json"}, embedding_function=None)

    def _add_chunks(self, collection, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
        for start in tqdm(range(0, len(chunks), CHROMA_BATCH_SIZE), desc="Saving to ChromaDB", unit="batch"):
            batch = chunks[start:start + CHROMA_BATCH_SIZE]
            batch_embeddings = embeddings[start:start + CHROMA_BATCH_SIZE]
            collection.add(ids=[chunk["id"] for chunk in batch], documents=[chunk["text"] for chunk in batch], metadatas=[self._chunk_metadata(chunk) for chunk in batch], embeddings=batch_embeddings)

    def _chunk_metadata(self, chunk: dict[str, Any]) -> dict[str, Any]:
        metadata = {key: value for key, value in chunk.items() if key not in {"id", "text"} and isinstance(value, (str, int, float, bool))}
        metadata["chunk_id"] = chunk["id"]
        return metadata

    def _chunk_id(self, document_id: str, article_number: str | int) -> str:
        source_hash = hashlib.sha1(str(document_id).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        return f"{source_hash}-chunk-{article_number}"