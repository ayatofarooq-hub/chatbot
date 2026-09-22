"""Build the persistent ChromaDB index from prepared legal text chunks."""

import json
import sys
from pathlib import Path

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError
from tqdm import tqdm

try:
    from .citation_registry import save_registry
    from .chunk_text import CHUNKS_FILE, build_chunks_from_document
    from .config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    from .ollama_client import client as ollama_client
    from backend.services.json_repository import JsonRepository
except ImportError:
    # Support direct execution with: python app/build_index.py
    from citation_registry import save_registry
    from chunk_text import CHUNKS_FILE, build_chunks_from_document
    from config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    from ollama_client import client as ollama_client
    from backend.services.json_repository import JsonRepository


COLLECTION_NAME = "iraqi_legal_documents"
EMBEDDING_BATCH_SIZE = 1
CHROMA_BATCH_SIZE = 100
REQUIRED_FIELDS = {
    "id",
    "source_file",
    "document_id",
    "page_number",
    "chunk_index",
    "text",
}
FULL_TEXT_METADATA_FIELDS = {
    "long_text",
    "body",
    "full_text",
    "original_long_text",
    "original_text",
}


def load_chunks(file_path: Path) -> list[dict]:
    """Read and validate chunk records from a JSON Lines file."""

    chunks = []

    with file_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number}: {error.msg}"
                ) from error

            missing_fields = REQUIRED_FIELDS - chunk.keys()
            if missing_fields:
                missing = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Line {line_number} is missing required fields: {missing}"
                )

            if not chunk["id"] or not chunk["text"]:
                raise ValueError(
                    f"Line {line_number} contains an empty id or text field."
                )

            chunks.append(chunk)

    if not chunks:
        raise ValueError("The chunks file does not contain any chunk records.")

    chunk_ids = [chunk["id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Chunk IDs must be unique before indexing.")

    return chunks


def create_embeddings(chunks: list[dict]) -> list[list[float]]:
    """Generate one Ollama embedding for every legal text chunk."""

    try:
        from .runtime_settings import runtime_settings
    except ImportError:
        from runtime_settings import runtime_settings
    model = runtime_settings()["model"]
    active_client = ollama.Client(
        host=model["ollama_base_url"], timeout=model["request_timeout"]
    )
    embeddings = []

    for start in tqdm(
        range(0, len(chunks), EMBEDDING_BATCH_SIZE),
        desc="Generating embeddings",
        unit="batch",
    ):
        batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
        response = active_client.embed(
            model=model["embedding_model"],
            input=[chunk.get("embedding_text") or chunk["text"] for chunk in batch],
            keep_alive=model["keep_alive"],
        )
        batch_embeddings = response["embeddings"]

        if len(batch_embeddings) != len(batch):
            raise RuntimeError(
                "Ollama returned a different number of embeddings than requested."
            )

        embeddings.extend(batch_embeddings)

    return embeddings


def reset_collection(client):
    """Delete the old collection, if present, and create an empty replacement."""

    try:
        client.delete_collection(COLLECTION_NAME)
    except NotFoundError:
        # The first index build has no existing collection to delete.
        pass

    return client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "embedding_model": EMBEDDING_MODEL,
            "schema_version": 2,
            "primary_source_format": "docx",
        },
        embedding_function=None,
    )


def chunk_metadata(chunk: dict) -> dict:
    """Return Chroma-compatible scalar metadata for one chunk."""

    metadata = {
        key: value
        for key, value in chunk.items()
        if key not in {"id", "text", "embedding_text", *FULL_TEXT_METADATA_FIELDS}
        and isinstance(value, (str, int, float, bool))
    }
    metadata["chunk_id"] = chunk["id"]
    return metadata


def add_chunks(collection, chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Store chunk documents, metadata, and embeddings in ChromaDB."""

    for start in tqdm(
        range(0, len(chunks), CHROMA_BATCH_SIZE),
        desc="Saving to ChromaDB",
        unit="batch",
    ):
        batch = chunks[start : start + CHROMA_BATCH_SIZE]
        batch_embeddings = embeddings[start : start + CHROMA_BATCH_SIZE]

        collection.add(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["text"] for chunk in batch],
            metadatas=[chunk_metadata(chunk) for chunk in batch],
            embeddings=batch_embeddings,
        )


def ensure_unique_chunk_ids(chunks: list[dict]) -> list[dict]:
    """Return chunks with Chroma-safe unique ids while preserving metadata links."""

    seen: dict[str, int] = {}
    unique_chunks = []
    for index, chunk in enumerate(chunks):
        updated = dict(chunk)
        original_id = str(updated.get("id") or updated.get("chunk_id") or f"chunk-{index}")
        count = seen.get(original_id, 0)
        seen[original_id] = count + 1
        if count:
            unique_id = f"{original_id}-dup-{count}"
            updated["original_chunk_id"] = original_id
            updated["id"] = unique_id
            updated["chunk_id"] = unique_id
            metadata = updated.get("metadata")
            if isinstance(metadata, dict):
                metadata = dict(metadata)
                metadata["original_chunk_id"] = original_id
                metadata["chunk_id"] = unique_id
                updated["metadata"] = metadata
        else:
            updated["id"] = original_id
            updated["chunk_id"] = str(updated.get("chunk_id") or original_id)
        unique_chunks.append(updated)
    return unique_chunks


def load_source_chunks() -> list[dict]:
    """Load and chunk JSON-backed legal records."""

    try:
        from . import chunk_text
        from .runtime_settings import runtime_settings
    except ImportError:
        import chunk_text
        from runtime_settings import runtime_settings
    retrieval = runtime_settings()["retrieval"]
    chunk_text.TARGET_CHUNK_SIZE = retrieval["chunk_size"]
    chunk_text.MIN_CHUNK_SIZE = max(100, int(retrieval["chunk_size"] * 0.6))
    chunk_text.MAX_CHUNK_SIZE = max(retrieval["chunk_size"] + 1, int(retrieval["chunk_size"] * 1.35))
    chunk_text.CHUNK_OVERLAP = retrieval["chunk_overlap"]
    repository = JsonRepository()
    documents = []
    for document in repository.list_documents():
        documents.append(document)
    if not documents:
        raise ValueError("No JSON legal records were found in data/legal_documents or dataset.")

    chunks = []
    for document in documents:
        document_chunks = build_chunks_from_document(document)
        chunks.extend(document_chunks)
        print(f"{document.get('source') or document.get('id')}: {len(document_chunks)} chunks")

    print(f"Loaded {len(documents)} JSON legal records.")

    if not chunks:
        raise ValueError("The source documents did not produce any chunks.")
    return ensure_unique_chunk_ids(chunks)


def save_chunks(chunks: list[dict]) -> None:
    """Save generated chunks for inspection and repeatable diagnostics."""

    with CHUNKS_FILE.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def main() -> None:
    """Build a fresh Chroma collection from JSON legal records."""

    try:
        chunks = load_source_chunks()
        save_chunks(chunks)
        print(f"Prepared {len(chunks)} chunks from configured legal sources.")
        print(f"Embedding model: {EMBEDDING_MODEL}")

        # Generate embeddings before resetting the collection. If Ollama is
        # unavailable, an existing working index remains untouched.
        embeddings = create_embeddings(chunks)

        CHROMA_FOLDER.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
        collection = reset_collection(client)
        add_chunks(collection, chunks, embeddings)
        save_registry(chunks)

        print(
            f"Indexed {collection.count()} chunks in "
            f"'{COLLECTION_NAME}' at {CHROMA_FOLDER}."
        )
    except FileNotFoundError as error:
        print(f"Index build failed: {error}")
        sys.exit(1)
    except ValueError as error:
        print(f"Index build failed: {error}")
        sys.exit(1)
    except ConnectionError:
        print("Index build failed: could not connect to Ollama.")
        print("Make sure the Ollama service is running.")
        sys.exit(1)
    except httpx.TimeoutException:
        print(
            "Index build failed: Ollama timed out after "
            f"{OLLAMA_REQUEST_TIMEOUT_SECONDS} seconds."
        )
        sys.exit(1)
    except ollama.ResponseError as error:
        print(f"Index build failed: Ollama request error: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"Index build failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
