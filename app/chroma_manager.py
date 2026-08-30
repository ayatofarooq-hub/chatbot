"""Comprehensive ChromaDB management for legal documents indexing and retrieval."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError
from tqdm import tqdm

from app.config import (
    CHROMA_FOLDER,
    EMBEDDING_MODEL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
)
from app.ollama_client import client as ollama_client


logger = logging.getLogger(__name__)

COLLECTION_NAME = "iraqi_legal_documents"
CHROMA_BATCH_SIZE = 100
EMBEDDING_BATCH_SIZE = 16


class ChromaManager:
    """Manage ChromaDB operations for legal documents."""

    def __init__(self, chroma_folder: Path = CHROMA_FOLDER):
        """Initialize ChromaDB client and connection."""
        self.chroma_folder = Path(chroma_folder)
        self.chroma_folder.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_folder))
        self.collection_name = COLLECTION_NAME

    def get_or_create_collection(self) -> chromadb.Collection:
        """Get existing collection or create new one."""
        try:
            collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"Connected to existing collection: {self.collection_name}")
            return collection
        except Exception as e:
            logger.warning(f"Collection not found: {e}, creating new one")
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Created new collection: {self.collection_name}")
            return collection

    def delete_collection(self) -> None:
        """Delete existing collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except NotFoundError:
            logger.warning(f"Collection not found: {self.collection_name}")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            collection = self.get_or_create_collection()
            count = collection.count()
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "status": "ready",
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e), "status": "error"}

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Ollama."""
        embeddings = []
        for i in tqdm(
            range(0, len(texts), EMBEDDING_BATCH_SIZE),
            desc="Generating embeddings",
        ):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            try:
                response = ollama_client.embed(
                    model=EMBEDDING_MODEL,
                    input=batch,
                    keep_alive=OLLAMA_KEEP_ALIVE,
                )
                embeddings.extend(response.embeddings)
            except httpx.ConnectError as e:
                logger.error(f"Failed to connect to Ollama: {e}")
                raise
            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
                raise
        return embeddings

    def add_documents(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> int:
        """Add chunks to ChromaDB collection."""
        if not chunks:
            logger.warning("No chunks to add")
            return 0

        collection = self.get_or_create_collection()

        # Generate embeddings if not provided
        if embeddings is None:
            texts = [chunk.get("text", "") for chunk in chunks]
            embeddings = self.generate_embeddings(texts)

        # Prepare data for ChromaDB
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk.get("text", "") for chunk in chunks]
        metadatas = [
            {
                "source_file": chunk.get("source_file", ""),
                "document_id": chunk.get("document_id", ""),
                "page_number": str(chunk.get("page_number", 0)),
                "chunk_index": str(chunk.get("chunk_index", 0)),
            }
            for chunk in chunks
        ]

        # Add to collection in batches
        added_count = 0
        for i in tqdm(
            range(0, len(chunks), CHROMA_BATCH_SIZE),
            desc="Adding to ChromaDB",
        ):
            batch_end = min(i + CHROMA_BATCH_SIZE, len(chunks))
            batch_ids = ids[i:batch_end]
            batch_documents = documents[i:batch_end]
            batch_embeddings = embeddings[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]

            collection.upsert(
                ids=batch_ids,
                documents=batch_documents,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
            )
            added_count += len(batch_ids)

        logger.info(f"Added {added_count} documents to ChromaDB")
        return added_count

    def search(
        self,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search ChromaDB for similar documents."""
        collection = self.get_or_create_collection()

        # Generate embedding if not provided
        if query_embedding is None:
            try:
                response = ollama_client.embed(
                    model=EMBEDDING_MODEL,
                    input=[query_text],
                    keep_alive=OLLAMA_KEEP_ALIVE,
                )
                query_embedding = response.embeddings[0]
            except Exception as e:
                logger.error(f"Error generating query embedding: {e}")
                return []

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["embeddings", "documents", "metadatas", "distances"],
            )

            # Format results
            formatted_results = []
            if results["ids"] and len(results["ids"]) > 0:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted_results.append(
                        {
                            "id": doc_id,
                            "text": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i],
                            "distance": results["distances"][0][i],
                        }
                    )

            return formatted_results
        except Exception as e:
            logger.error(f"Error searching collection: {e}")
            return []

    def delete_by_id(self, doc_ids: List[str]) -> int:
        """Delete documents from collection by ID."""
        collection = self.get_or_create_collection()
        try:
            collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents from ChromaDB")
            return len(doc_ids)
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            return 0

    def delete_by_source(self, source_file: str) -> int:
        """Delete all documents from a specific source file."""
        collection = self.get_or_create_collection()
        try:
            # Get all documents with matching source
            results = collection.get(
                where={"source_file": {"$eq": source_file}},
                include=[],
            )

            if results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} documents from source: {source_file}"
                )
                return len(results["ids"])

            return 0
        except Exception as e:
            logger.error(f"Error deleting by source: {e}")
            return 0

    def clear_all(self) -> None:
        """Clear all documents from collection."""
        self.delete_collection()
        self.get_or_create_collection()
        logger.info("Cleared all documents from ChromaDB")

    def export_to_json(self, output_path: Path) -> None:
        """Export collection to JSON file."""
        collection = self.get_or_create_collection()
        try:
            results = collection.get(include=["documents", "metadatas"])
            export_data = {
                "collection_name": self.collection_name,
                "total_documents": len(results["ids"]),
                "documents": [
                    {
                        "id": doc_id,
                        "text": results["documents"][i],
                        "metadata": results["metadatas"][i],
                    }
                    for i, doc_id in enumerate(results["ids"])
                ],
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported collection to {output_path}")
        except Exception as e:
            logger.error(f"Error exporting collection: {e}")

    def import_from_json(self, input_path: Path) -> int:
        """Import documents from JSON file."""
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            chunks = []
            for doc in import_data.get("documents", []):
                chunks.append(
                    {
                        "id": doc["id"],
                        "text": doc["text"],
                        **doc.get("metadata", {}),
                    }
                )

            return self.add_documents(chunks)
        except Exception as e:
            logger.error(f"Error importing from JSON: {e}")
            return 0

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document by ID."""
        collection = self.get_or_create_collection()
        try:
            results = collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )

            if results["ids"]:
                return {
                    "id": results["ids"][0],
                    "text": results["documents"][0],
                    "metadata": results["metadatas"][0],
                }

            return None
        except Exception as e:
            logger.error(f"Error retrieving document: {e}")
            return None

    def list_all_documents(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all documents in collection."""
        collection = self.get_or_create_collection()
        try:
            results = collection.get(include=["documents", "metadatas"])

            documents = []
            for i, doc_id in enumerate(results["ids"]):
                documents.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][i],
                        "metadata": results["metadatas"][i],
                    }
                )

            if limit:
                return documents[:limit]

            return documents
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []


# Global manager instance
_manager: Optional[ChromaManager] = None


def get_chroma_manager() -> ChromaManager:
    """Get or create global ChromaManager instance."""
    global _manager
    if _manager is None:
        _manager = ChromaManager()
    return _manager


# Convenience functions for common operations
def initialize_chroma() -> ChromaManager:
    """Initialize ChromaDB manager."""
    return get_chroma_manager()


def get_chroma_stats() -> Dict[str, Any]:
    """Get ChromaDB collection statistics."""
    return get_chroma_manager().get_collection_stats()


def search_chroma(
    query_text: str, n_results: int = 5
) -> List[Dict[str, Any]]:
    """Search ChromaDB for similar documents."""
    return get_chroma_manager().search(query_text, n_results=n_results)


def add_to_chroma(chunks: List[Dict[str, Any]]) -> int:
    """Add chunks to ChromaDB."""
    return get_chroma_manager().add_documents(chunks)


def clear_chroma() -> None:
    """Clear all documents from ChromaDB."""
    get_chroma_manager().clear_all()


if __name__ == "__main__":
    # Example usage
    manager = ChromaManager()
    print("ChromaDB Manager initialized")
    print(f"Stats: {manager.get_collection_stats()}")
