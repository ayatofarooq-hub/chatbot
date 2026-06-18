"""Create Arabic legal chunks from structured source documents."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

try:
    from .config import LEGAL_DOCUMENTS_FOLDER, PROJECT_ROOT
    from .document_loaders import (
        DocumentBlock,
        LoadedDocument,
        load_document,
        load_documents,
    )
except ImportError:
    from config import LEGAL_DOCUMENTS_FOLDER, PROJECT_ROOT
    from document_loaders import (
        DocumentBlock,
        LoadedDocument,
        load_document,
        load_documents,
    )


CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks.jsonl"
MIN_CHUNK_SIZE = 650
TARGET_CHUNK_SIZE = 1100
MAX_CHUNK_SIZE = 1500
CHUNK_OVERLAP = 120
BOUNDARY_PATTERNS = (
    re.compile(r"\n\n"),
    re.compile(r"(?<=[.!؟؛:])\s+"),
    re.compile(r"\n"),
    re.compile(r"\s"),
)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace without changing Arabic legal wording."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def choose_chunk_end(text: str, start: int) -> int:
    """Choose a readable legal-text boundary near the target size."""

    if len(text) - start <= MAX_CHUNK_SIZE:
        return len(text)

    minimum_end = start + MIN_CHUNK_SIZE
    target_end = start + TARGET_CHUNK_SIZE
    maximum_end = min(start + MAX_CHUNK_SIZE, len(text))
    for pattern in BOUNDARY_PATTERNS:
        candidates = [
            match.end()
            for match in pattern.finditer(text, minimum_end, maximum_end)
        ]
        if candidates:
            return min(candidates, key=lambda value: abs(value - target_end))
    return maximum_end


def choose_next_start(text: str, chunk_end: int) -> int:
    """Apply a small overlap without beginning inside a word."""

    desired_start = max(0, chunk_end - CHUNK_OVERLAP)
    boundaries = [
        position + 1
        for position in (
            text.find(" ", desired_start, chunk_end),
            text.find("\n", desired_start, chunk_end),
        )
        if position != -1
    ]
    return min(boundaries) if boundaries else desired_start


def split_text(text: str) -> list[str]:
    """Split oversized text while preserving legal sentence boundaries."""

    text = normalize_whitespace(text)
    chunks = []
    start = 0
    while start < len(text):
        end = choose_chunk_end(text, start)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = choose_next_start(text, end)
    return chunks


def _reference_label(
    article_reference: str,
    section_reference: str,
    section_title: str,
) -> str:
    return article_reference or section_reference or section_title


def _chunk_id(source_file: str, chunk_index: int) -> str:
    source_hash = hashlib.sha1(
        source_file.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]
    return f"{source_hash}-chunk-{chunk_index}"


def build_chunks_from_document(document: LoadedDocument) -> list[dict]:
    """Build embedding chunks while retaining legal structure and metadata."""

    chunks = []
    heading_path: list[str] = []
    current_article = ""
    current_section = ""

    for block in document.blocks:
        if block.block_type == "heading":
            level = max(block.heading_level or 1, 1)
            heading_path = heading_path[: level - 1]
            heading_path.append(block.text)
            if block.article_reference:
                current_article = block.article_reference
            if block.section_reference:
                current_section = block.section_reference
            continue

        if block.article_reference:
            current_article = block.article_reference
        if block.section_reference:
            current_section = block.section_reference

        section_title = " > ".join(heading_path)
        context_lines = []
        if document.title and document.title != section_title:
            context_lines.append(document.title)
        if section_title:
            context_lines.append(section_title)
        if block.block_type == "table":
            context_lines.append("[جدول]")

        prefix = "\n".join(context_lines)
        available_size = max(MIN_CHUNK_SIZE, MAX_CHUNK_SIZE - len(prefix) - 2)
        block_parts = (
            split_text(block.text)
            if len(block.text) > available_size
            else [block.text]
        )

        for part in block_parts:
            text = "\n\n".join(value for value in (prefix, part) if value)
            chunk_index = len(chunks)
            legal_reference = _reference_label(
                current_article,
                current_section,
                section_title,
            )
            chunk = {
                "id": _chunk_id(document.source_file, chunk_index),
                "source_file": document.source_file,
                "source_type": document.source_type,
                "document_title": document.title,
                "page_number": block.page_number,
                "chunk_index": chunk_index,
                "section_title": section_title,
                "article_reference": current_article,
                "section_reference": current_section,
                "legal_reference": legal_reference,
                "block_type": block.block_type,
                "text": text,
            }
            chunk.update(
                {
                    f"document_{key}": value
                    for key, value in document.metadata.items()
                    if value
                }
            )
            chunks.append(chunk)

    return chunks


def build_chunks(file_path: Path) -> list[dict]:
    """Build chunks for one supported source document."""

    return build_chunks_from_document(load_document(file_path))


def build_chunks_from_content(source_file: str, content: str) -> list[dict]:
    """Build chunks from API-provided plain text without changing its contract."""

    normalized = normalize_whitespace(content)
    page_pattern = re.compile(r"^--- PAGE (\d+) ---\s*$", re.MULTILINE)
    separators = list(page_pattern.finditer(normalized))
    blocks = []

    if not separators:
        separators = list(
            page_pattern.finditer(f"--- PAGE 1 ---\n{normalized}")
        )
        normalized = f"--- PAGE 1 ---\n{normalized}"

    for index, separator in enumerate(separators):
        end = (
            separators[index + 1].start()
            if index + 1 < len(separators)
            else len(normalized)
        )
        page_number = int(separator.group(1))
        page_text = normalized[separator.end() : end].strip()
        if page_text:
            blocks.append(
                DocumentBlock(text=page_text, page_number=page_number)
            )

    document = LoadedDocument(
        source_file=source_file,
        source_type="txt",
        title=Path(source_file).stem,
        blocks=blocks,
    )
    return build_chunks_from_document(document)


def main() -> None:
    """Load and chunk every DOCX/TXT source document as JSON Lines."""

    documents = load_documents(LEGAL_DOCUMENTS_FOLDER)
    if not documents:
        print(f"No DOCX or TXT files found in: {LEGAL_DOCUMENTS_FOLDER}")
        return

    all_chunks = []
    for document in documents:
        document_chunks = build_chunks_from_document(document)
        all_chunks.extend(document_chunks)
        print(f"{document.source_file}: {len(document_chunks)} chunks")

    with CHUNKS_FILE.open("w", encoding="utf-8") as output_file:
        for chunk in all_chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Total chunks: {len(all_chunks)}")
    print(f"Saved to: {CHUNKS_FILE}")


if __name__ == "__main__":
    main()
