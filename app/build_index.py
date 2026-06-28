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
    from .postgres_laws import load_postgres_documents
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
    from postgres_laws import load_postgres_documents


COLLECTION_NAME = "iraqi_legal_documents"
EMBEDDING_BATCH_SIZE = 16
CHROMA_BATCH_SIZE = 100
REQUIRED_FIELDS = {
    "id",
    "source_file",
    "page_number",
    "chunk_index",
    "text",
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
            input=[chunk["text"] for chunk in batch],
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
        if key not in {"id", "text"}
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


def load_source_chunks() -> list[dict]:
    """Load and chunk PostgreSQL legal records."""

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
    documents = load_postgres_documents()
    if not documents:
        raise ValueError(
            "PostgreSQL public.iraqi_laws returned no legal records. "
            "Check DATABASE_URL and the table contents."
        )

    chunks = []
    for document in documents:
        document_chunks = build_chunks_from_document(document)
        chunks.extend(document_chunks)
        print(f"{document.source_file}: {len(document_chunks)} chunks")

    print(f"Loaded {len(documents)} rows from PostgreSQL public.iraqi_laws.")

    if not chunks:
        raise ValueError("The source documents did not produce any chunks.")
    return chunks


def save_chunks(chunks: list[dict]) -> None:
    """Save generated chunks for inspection and repeatable diagnostics."""

    with CHUNKS_FILE.open("w", encoding="utf-8") as output_file:
        for chunk in chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")


def main() -> None:
    """Build a fresh Chroma collection from PostgreSQL legal records."""

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
