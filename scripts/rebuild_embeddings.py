from __future__ import annotations

from backend.services.embedding_service import EmbeddingService


def main() -> None:
    service = EmbeddingService()
    count = service.rebuild()
    print(f"Rebuilt ChromaDB index with {count} chunks.")


if __name__ == "__main__":
    main()
