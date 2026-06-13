"""Diagnostic search for testing retrieval quality in the legal index."""

import argparse
import sys

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError

try:
    from .build_index import COLLECTION_NAME
    from .config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from .ollama_client import client as ollama_client
except ImportError:
    # Support direct execution with: python app/search_index.py
    from build_index import COLLECTION_NAME
    from config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from ollama_client import client as ollama_client


RESULT_COUNT = 5
TEXT_PREVIEW_LENGTH = 500


def get_question() -> str:
    """Read a question from a command argument or an interactive prompt."""

    parser = argparse.ArgumentParser(
        description="Search the Iraqi legal ChromaDB index."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Arabic legal question to search for.",
    )
    arguments = parser.parse_args()

    question = " ".join(arguments.question).strip()
    if not question:
        question = input("Enter an Arabic legal question: ").strip()

    if not question:
        raise ValueError("The question cannot be empty.")

    return question


def search(question: str) -> dict:
    """Embed the question and return the closest indexed chunks."""

    embedding_response = ollama_client.embed(
        model=EMBEDDING_MODEL,
        input=question,
        keep_alive=EMBEDDING_QUERY_KEEP_ALIVE,
    )
    question_embedding = embedding_response["embeddings"][0]

    client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )

    if collection.count() == 0:
        raise ValueError("The legal document collection is empty.")

    return collection.query(
        query_embeddings=[question_embedding],
        n_results=min(RESULT_COUNT, collection.count()),
        include=["documents", "metadatas", "distances"],
    )


def print_results(results: dict) -> None:
    """Print ranked retrieval results with source metadata."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        print("No matching chunks were found.")
        return

    print()
    print("Top retrieval results")
    print("=" * 70)

    for rank, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        distance = distances[rank - 1] if rank <= len(distances) else None
        preview = document[:TEXT_PREVIEW_LENGTH]

        print(f"Rank: {rank}")
        print(f"Source file: {metadata.get('source_file', 'Unknown')}")
        print(f"Page number: {metadata.get('page_number', 'Unknown')}")
        if distance is not None:
            print(f"Distance: {distance:.6f}")
        print("Text preview:")
        print(preview)
        print("-" * 70)


def main() -> None:
    """Run one retrieval-quality test without calling the chat model."""

    try:
        question = get_question()
        results = search(question)
        print_results(results)
    except (EOFError, KeyboardInterrupt):
        print("\nSearch cancelled.")
        sys.exit(1)
    except ValueError as error:
        print(f"Search failed: {error}")
        sys.exit(1)
    except NotFoundError:
        print(
            f"Search failed: collection '{COLLECTION_NAME}' was not found. "
            "Run python app/build_index.py first."
        )
        sys.exit(1)
    except ConnectionError:
        print("Search failed: could not connect to Ollama.")
        print("Make sure the Ollama service is running.")
        sys.exit(1)
    except httpx.TimeoutException:
        print("Search failed: the Ollama embedding request timed out.")
        sys.exit(1)
    except ollama.ResponseError as error:
        print(f"Search failed: Ollama request error: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"Search failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
