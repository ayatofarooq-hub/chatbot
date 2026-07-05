from __future__ import annotations

from pathlib import Path

from backend.services.document_service import DocumentService

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "legal_documents"


def main() -> None:
    service = DocumentService()
    imported = service.import_directory(SOURCE_DIR)
    print(f"Imported {len(imported)} documents from Word files into JSON storage.")


if __name__ == "__main__":
    main()
