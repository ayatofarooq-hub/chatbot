from __future__ import annotations

from pathlib import Path

from backend.services.json_repository import JsonRepository


def validate_repository() -> None:
    repository = JsonRepository()
    documents = repository.list_documents()
    if not documents:
        raise SystemExit("No JSON legal documents were found.")
    seen_ids = set()
    for document in documents:
        doc_id = document.get("id")
        if not doc_id:
            raise SystemExit("A document is missing an id.")
        if doc_id in seen_ids:
            raise SystemExit(f"Duplicate id detected: {doc_id}")
        seen_ids.add(doc_id)
        if not document.get("title"):
            raise SystemExit(f"Document {doc_id} is missing a title.")
        articles = document.get("articles", [])
        if not isinstance(articles, list) or not articles:
            raise SystemExit(f"Document {doc_id} has no articles.")
        for index, article in enumerate(articles, start=1):
            if not article.get("text"):
                raise SystemExit(f"Document {doc_id} article {index} is missing text.")
    print(f"Validated {len(documents)} documents and {sum(len(doc.get('articles', [])) for doc in documents)} articles.")


if __name__ == "__main__":
    validate_repository()
