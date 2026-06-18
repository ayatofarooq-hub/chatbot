"""Temporary project entry point.

This file checks the initial setup only. The legal chatbot and RAG pipeline
will be implemented later.
"""

from app.config import (
    CHAT_MODEL,
    CHROMA_FOLDER,
    EMBEDDING_MODEL,
    EXTRACTED_TEXT_FOLDER,
    LEGAL_DOCUMENTS_FOLDER,
    create_data_directories,
)


def main() -> None:
    """Prepare local folders and display the current configuration."""

    create_data_directories()

    print("Offline Arabic legal chatbot project is ready for development.")
    print(f"Legal documents folder: {LEGAL_DOCUMENTS_FOLDER}")
    print(f"Extracted text folder: {EXTRACTED_TEXT_FOLDER}")
    print(f"Chroma folder: {CHROMA_FOLDER}")
    print(f"Chat model: {CHAT_MODEL}")
    print(f"Embedding model: {EMBEDDING_MODEL}")


if __name__ == "__main__":
    main()
