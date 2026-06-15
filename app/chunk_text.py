"""Split extracted legal text into page-aware chunks for future RAG use."""

import json
import re
from pathlib import Path

try:
    from .config import EXTRACTED_TEXT_FOLDER, PROJECT_ROOT
except ImportError:
    # Support the requested direct command: python app/chunk_text.py
    from config import EXTRACTED_TEXT_FOLDER, PROJECT_ROOT


CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks.jsonl"
MIN_CHUNK_SIZE = 800
TARGET_CHUNK_SIZE = 1000
MAX_CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

PAGE_SEPARATOR_PATTERN = re.compile(
    r"^--- PAGE (\d+) ---\s*$",
    flags=re.MULTILINE,
)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace without changing Arabic legal wording."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_pages(file_path: Path) -> list[tuple[int, str]]:
    """Return the page number and text for every page in an extracted file."""

    content = file_path.read_text(encoding="utf-8")
    separators = list(PAGE_SEPARATOR_PATTERN.finditer(content))
    pages = []

    for index, separator in enumerate(separators):
        page_number = int(separator.group(1))
        page_start = separator.end()
        page_end = (
            separators[index + 1].start()
            if index + 1 < len(separators)
            else len(content)
        )
        page_text = normalize_whitespace(content[page_start:page_end])

        if page_text:
            pages.append((page_number, page_text))

    return pages


def choose_chunk_end(text: str, start: int) -> int:
    """Choose a readable boundary near the target chunk size."""

    remaining_length = len(text) - start
    if remaining_length <= MAX_CHUNK_SIZE:
        return len(text)

    minimum_end = start + MIN_CHUNK_SIZE
    target_end = start + TARGET_CHUNK_SIZE
    maximum_end = min(start + MAX_CHUNK_SIZE, len(text))

    # Legal text is kept unchanged. We only prefer existing paragraph,
    # sentence, line, or word boundaries instead of cutting through a word.
    boundary_patterns = (
        re.compile(r"\n\n"),
        re.compile(r"[.!؟؛:]\s"),
        re.compile(r"\n"),
        re.compile(r"\s"),
    )

    for pattern in boundary_patterns:
        candidates = [
            match.end()
            for match in pattern.finditer(text, minimum_end, maximum_end)
        ]
        if candidates:
            return min(candidates, key=lambda position: abs(position - target_end))

    return maximum_end


def choose_next_start(text: str, chunk_end: int) -> int:
    """Start the next chunk near a 150-character overlap at a word boundary."""

    desired_start = max(0, chunk_end - CHUNK_OVERLAP)
    next_space = text.find(" ", desired_start, chunk_end)
    next_newline = text.find("\n", desired_start, chunk_end)
    boundaries = [
        position + 1
        for position in (next_space, next_newline)
        if position != -1
    ]

    return min(boundaries) if boundaries else desired_start


def split_page(page_text: str) -> list[str]:
    """Split one page into overlapping chunks without summarizing its text."""

    chunks = []
    start = 0

    while start < len(page_text):
        end = choose_chunk_end(page_text, start)
        chunk = page_text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(page_text):
            break

        next_start = choose_next_start(page_text, end)
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def build_chunks(file_path: Path) -> list[dict]:
    """Build serializable chunks for one extracted text file."""

    return build_chunks_from_content(
        source_file=file_path.name,
        content=file_path.read_text(encoding="utf-8"),
    )


def build_chunks_from_content(source_file: str, content: str) -> list[dict]:
    """Build chunks from API-provided page-separated document content."""

    chunks = []
    chunk_index = 0
    source_id = Path(source_file).stem
    separators = list(PAGE_SEPARATOR_PATTERN.finditer(content))

    if not separators:
        content = f"--- PAGE 1 ---\n{content}"
        separators = list(PAGE_SEPARATOR_PATTERN.finditer(content))

    pages = []
    for index, separator in enumerate(separators):
        page_number = int(separator.group(1))
        page_start = separator.end()
        page_end = (
            separators[index + 1].start()
            if index + 1 < len(separators)
            else len(content)
        )
        page_text = normalize_whitespace(content[page_start:page_end])
        if page_text:
            pages.append((page_number, page_text))

    for page_number, page_text in pages:
        for chunk_text in split_page(page_text):
            chunks.append(
                {
                    "id": f"{source_id}-page-{page_number}-chunk-{chunk_index}",
                    "source_file": source_file,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                }
            )
            chunk_index += 1

    return chunks


def main() -> None:
    """Chunk every extracted text file and save the result as JSON Lines."""

    text_files = sorted(EXTRACTED_TEXT_FOLDER.glob("*.txt"))
    all_chunks = []

    if not text_files:
        print(f"No text files found in: {EXTRACTED_TEXT_FOLDER}")
        return

    for file_path in text_files:
        file_chunks = build_chunks(file_path)
        all_chunks.extend(file_chunks)
        print(f"{file_path.name}: {len(file_chunks)} chunks")

    with CHUNKS_FILE.open("w", encoding="utf-8") as output_file:
        for chunk in all_chunks:
            output_file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Total chunks: {len(all_chunks)}")
    print(f"Saved to: {CHUNKS_FILE}")


if __name__ == "__main__":
    main()
