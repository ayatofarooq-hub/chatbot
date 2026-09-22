"""Create Arabic legal chunks from structured source documents."""

from __future__ import annotations

import hashlib
import json
import re
from types import SimpleNamespace

try:
    from .config import PROJECT_ROOT
    from .arabic_search import normalized_search_blob
    from .legal_source_text import source_text_from_payload
    from .legal_document import DocumentBlock, LoadedDocument
except ImportError:
    from config import PROJECT_ROOT
    from arabic_search import normalized_search_blob
    from legal_source_text import source_text_from_payload
    from legal_document import DocumentBlock, LoadedDocument


CHUNKS_FILE = PROJECT_ROOT / "data" / "chunks.jsonl"
MIN_CHUNK_SIZE = 650
TARGET_CHUNK_SIZE = 1100
MAX_CHUNK_SIZE = 1500
CHUNK_OVERLAP = 120
SUMMARY_SECTION_LABELS = ("الشرح التفصيلي", "الشرح التفصيلى")
SUMMARY_CONTEXT_VALUES = {"summary", "ملخص", "الملخص", "الخلاصة", "الشرح", "التفصيلي", "التفصيلى"}
SUMMARY_SECTION_PATTERN = re.compile(
    r"^\s*(?:summary|ملخص|الملخص|الخلاصة|الشرح التفصيلي|الشرح التفصيلى)\s*[:：\-]?",
    re.IGNORECASE,
)
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


def strip_summary_sections(text: str) -> str:
    """Remove generated summary/explanation lines before chunking."""

    cleaned_lines = []
    for line in str(text or "").splitlines():
        if SUMMARY_SECTION_PATTERN.match(line) or any(label in line for label in SUMMARY_SECTION_LABELS):
            continue
        cleaned_lines.append(line)
    return normalize_whitespace("\n".join(cleaned_lines))


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


def _reference_label(article_reference: str, section_reference: str, section_title: str) -> str:
    return article_reference or section_reference or section_title


def _chunk_id(source_file: str, chunk_index: int) -> str:
    source_hash = hashlib.sha1(source_file.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"{source_hash}-chunk-{chunk_index}"


def _has_value(value) -> bool:
    return value not in (None, "") and value != [] and value != {}


def _flatten_metadata_values(value) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_flatten_metadata_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_flatten_metadata_values(item))
    else:
        text = str(value or "").strip()
        if text:
            values.append(text)
    return values


def _metadata_context_value(value: str) -> str:
    text = strip_summary_sections(value)
    if text.strip().lower() in SUMMARY_CONTEXT_VALUES:
        return ""
    return text


def _unique_join(values: list[str], limit: int = 20) -> str:
    """Return Chroma-safe scalar metadata from ordered extracted values."""

    cleaned = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .،؛:")
        if text and text not in cleaned:
            cleaned.append(text)
    return " | ".join(cleaned[:limit])


def _first_value(*values) -> str:
    for value in values:
        if isinstance(value, list):
            text = _unique_join(_flatten_metadata_values(value), limit=1)
        elif isinstance(value, dict):
            text = _unique_join(_flatten_metadata_values(value), limit=1)
        else:
            text = str(value or "").strip()
        if text:
            return text
    return ""


def _nested_mapping(document: dict, key: str) -> dict:
    value = document.get(key)
    return value if isinstance(value, dict) else {}


def _extract_dates(text: str) -> list[str]:
    return re.findall(r"\b[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4}\b", text)


def _extract_session_date(text: str) -> str:
    """Extract the date tied specifically to a session phrase."""

    normalized = re.sub(r"\s+", " ", str(text or ""))
    patterns = (
        r"(?:الجلسة|جلسته|جلسة)\s+.{0,140}?\s+المنعقد(?:ة)?\s+(?:في|بتاريخ)\s+([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4})",
        r"(?:الجلسة|جلسته|جلسة)\s+.{0,140}?\s+(?:في|بتاريخ)\s+([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4})",
        r"(?:عقدت|انعقدت)\s+.{0,80}?(?:الجلسة|جلسة)\s+.{0,80}?(?:في|بتاريخ)\s+([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4})",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return re.sub(r"\s+", "", match.group(1))
    return ""


def _extract_reference_numbers(text: str) -> list[str]:
    patterns = (
        r"المرقم\s+بالعدد\s*\(\s*([^)]+?)\s*\)",
        r"بالعدد\s*\(\s*([^)]+?)\s*\)",
        r"رقم\s+الكتاب\s*\(?\s*([0-9٠-٩A-Za-z/\\-]+)\s*\)?",
    )
    values: list[str] = []
    for pattern in patterns:
        values.extend(match.strip() for match in re.findall(pattern, text))
    return values


def _extract_recommendation_numbers(text: str) -> list[str]:
    patterns = (
        r"توصية\s+المجلس\s+الوزاري\s+للاقتصاد\s*\(\s*([^)]+?)\s*\)",
        r"التوصية\s*\(\s*([0-9٠-٩]+\s*ق?)\s*\)",
    )
    values: list[str] = []
    for pattern in patterns:
        values.extend(match.strip() for match in re.findall(pattern, text))
    return values


def _extract_entities(text: str) -> list[str]:
    pattern = re.compile(
        r"\b(?:وزارة|شركة|مجلس|هيئة|دائرة|محافظة|لجنة|الأمانة العامة)\s+[\u0600-\u06ffA-Za-z0-9\s]{2,60}",
    )
    entities = []
    for match in pattern.finditer(text):
        entity = re.split(r"[،؛:.\n\r]", match.group(0), 1)[0]
        entity = re.sub(r"\s+", " ", entity).strip()
        if entity:
            entities.append(entity)
    return entities


def _extract_amounts(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", match.group(0)).strip()
        for match in re.finditer(r"[0-9٠-٩][0-9٠-٩.,/ ]*\s*(?:دينار|دولار)", text)
    ]


def _extract_explicit_decision_number(document: dict, text: str) -> str:
    """Return decision number only from explicit decision fields or phrase."""

    info = _nested_mapping(document, "document")
    metadata = _nested_mapping(document, "metadata")
    extracted = _nested_mapping(document, "extracted_fields")
    value = _first_value(
        document.get("decision_number"),
        info.get("decision_number"),
        metadata.get("decision_number"),
        extracted.get("decision_number"),
        extracted.get("decision_numbers"),
    )
    if value and value.lower() not in {"none", "null"}:
        return value
    match = re.search(r"قرار\s+مجلس\s+الوزراء\s+رقم\s*\(?\s*([0-9٠-٩]+)\s*\)?", text)
    return match.group(1).strip() if match else ""


def _derived_metadata(document: dict, text: str) -> dict[str, str]:
    """Extract searchable scalar metadata used by retrieval and direct answers."""

    info = _nested_mapping(document, "document")
    metadata = _nested_mapping(document, "metadata")
    extracted = _nested_mapping(document, "extracted_fields")
    references = document.get("references")
    legal_entities = document.get("legal_entities")
    values = {
        "decision_number": _extract_explicit_decision_number(document, text),
        "issue_date": _first_value(document.get("issue_date"), info.get("issue_date"), metadata.get("issue_date"), extracted.get("issue_date")),
        "session_date": _first_value(
            document.get("session_date"),
            info.get("session_date"),
            metadata.get("session_date"),
            extracted.get("session_date"),
            _extract_session_date(text),
        ),
        "session_number": _first_value(document.get("session_number"), info.get("session_number"), metadata.get("session_number"), extracted.get("session_number")),
        "year": _first_value(document.get("year"), info.get("year"), metadata.get("year"), extracted.get("year")),
        "reference_numbers": _first_value(
            document.get("reference_numbers"),
            metadata.get("reference_numbers"),
            extracted.get("reference_numbers"),
            _extract_reference_numbers(text),
        ),
        "recommendation_numbers": _first_value(
            document.get("recommendation_numbers"),
            metadata.get("recommendation_numbers"),
            extracted.get("recommendation_numbers"),
            _extract_recommendation_numbers(text),
        ),
        "dates": _first_value(document.get("dates"), metadata.get("dates"), extracted.get("dates"), _extract_dates(text)),
        "entities": _first_value(
            document.get("entities"),
            metadata.get("entities"),
            extracted.get("entities"),
            legal_entities,
            _extract_entities(text),
        ),
        "amounts": _first_value(document.get("amounts"), metadata.get("amounts"), extracted.get("amounts"), _extract_amounts(text)),
        "references": _first_value(references),
    }
    return {key: value for key, value in values.items() if value and value.lower() not in {"none", "null"}}


def _metadata_search_context(document: dict) -> str:
    values: list[str] = []
    for key in (
        "title",
        "document_type",
        "law_number",
        "year",
        "category",
        "keywords",
        "legal_references",
        "references",
        "legal_entities",
        "metadata",
        "extracted_fields",
    ):
        values.extend(_metadata_context_value(value) for value in _flatten_metadata_values(document.get(key)))
    source = document.get("source") if isinstance(document.get("source"), dict) else {}
    info = document.get("document") if isinstance(document.get("document"), dict) else {}
    values.extend(_metadata_context_value(value) for value in _flatten_metadata_values(info))
    values.extend(_metadata_context_value(value) for value in _flatten_metadata_values(source.get("parser")))
    raw_context = " | ".join(dict.fromkeys(value for value in values if value))[:1200]
    normalized_context = normalized_search_blob(raw_context)
    return "\n".join(
        dict.fromkeys(value for value in (raw_context, normalized_context) if value)
    )


def _embedding_text(text: str, search_context: str) -> str:
    if not search_context:
        return text
    return f"{search_context}\n\n{text}".strip()


def _normalize_document(document) -> SimpleNamespace:
    if isinstance(document, dict):
        blocks = []
        source = document.get("source") if isinstance(document.get("source"), dict) else {}
        document_info = document.get("document") if isinstance(document.get("document"), dict) else {}
        document_id = str(
            document.get("id")
            or document.get("document_id")
            or document_info.get("id")
            or source.get("filename")
            or document.get("source")
            or "document"
        )
        original_json_path = str(
            document.get("original_json_path")
            or document.get("source_json_path")
            or document.get("json_path")
            or document.get("path")
            or ""
        )
        primary_text = strip_summary_sections(source_text_from_payload(document))
        if primary_text:
            blocks.append(DocumentBlock(text=primary_text))
        else:
            for article in document.get("articles", []) or []:
                article_text = strip_summary_sections(article.get("text", "") or "")
                if article_text:
                    blocks.append(
                        DocumentBlock(
                            text=article_text,
                            article_reference=str(article.get("article_number", "")),
                        )
                    )
        if not blocks:
            fallback_text = strip_summary_sections(
                document.get("content")
                or document.get("embedding_text")
                or document.get("text")
                or ""
            )
            if fallback_text:
                blocks.append(DocumentBlock(text=fallback_text))
        source_file = str(
            document.get("source_file")
            or source.get("filename")
            or document.get("source")
            or document.get("id")
            or "document"
        )
        metadata_text_source = "\n".join(block.text for block in blocks)
        return SimpleNamespace(
            source_file=source_file,
            source_type="json",
            title=str(document.get("title") or document_info.get("title") or ""),
            document_id=document_id,
            original_json_path=original_json_path,
            has_full_source_text=bool(primary_text),
            blocks=blocks,
            document_type=str(document.get("document_type") or document_info.get("type") or ""),
            search_context=_metadata_search_context(document),
            metadata={
                **_derived_metadata(document, metadata_text_source),
                **{
                    k: v
                    for k, v in document.items()
                    if k not in {"title", "articles", "summary", "content", "embedding_text", "long_text", "body"}
                    and _has_value(v)
                },
            },
        )
    return document


DIRECT_CHUNK_METADATA_KEYS = {
    "decision_number",
    "issue_date",
    "session_date",
    "session_number",
    "year",
    "reference_numbers",
    "recommendation_numbers",
    "dates",
    "entities",
    "amounts",
}


def _direct_chunk_metadata(metadata: dict) -> dict[str, str]:
    """Expose high-value document metadata without the document_ prefix."""

    return {
        key: str(metadata[key])
        for key in DIRECT_CHUNK_METADATA_KEYS
        if metadata.get(key) not in (None, "", [], {})
        and isinstance(metadata.get(key), (str, int, float, bool))
    }


def _document_chunk_metadata(metadata: dict) -> dict[str, str | int | float | bool]:
    """Keep chunk JSON metadata scalar and free of generated summaries."""

    cleaned = {}
    for key, value in metadata.items():
        if value in (None, "", [], {}) or not isinstance(value, (str, int, float, bool)):
            continue
        if isinstance(value, str):
            value = _metadata_context_value(value)
            if not value:
                continue
        cleaned[f"document_{key}"] = value
    return cleaned


def build_chunks_from_document(document: LoadedDocument | dict) -> list[dict]:
    """Build embedding chunks while retaining legal structure and metadata."""

    doc = _normalize_document(document)
    search_context = getattr(doc, "search_context", "")
    chunks = []
    heading_path: list[str] = []
    current_article = ""
    current_section = ""

    for block in doc.blocks:
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
        if doc.title and doc.title != section_title:
            context_lines.append(doc.title)
        if section_title:
            context_lines.append(section_title)
        if block.block_type == "table":
            context_lines.append("[جدول]")

        block_text = strip_summary_sections(block.text)
        if not block_text:
            continue
        prefix = "\n".join(context_lines)
        available_size = max(MIN_CHUNK_SIZE, MAX_CHUNK_SIZE - len(prefix) - 2)
        block_parts = split_text(block_text) if len(block_text) > available_size else [block_text]

        for part in block_parts:
            text = "\n\n".join(value for value in (prefix, part) if value)
            chunk_index = len(chunks)
            legal_reference = _reference_label(current_article, current_section, section_title)
            chunk = {
                "id": _chunk_id(doc.source_file, chunk_index),
                "source_file": doc.source_file,
                "source_filename": doc.source_file,
                "document_id": getattr(doc, "document_id", "") or doc.metadata.get("document_id", ""),
                "original_json_path": getattr(doc, "original_json_path", "") or doc.metadata.get("original_json_path", ""),
                "json_path": getattr(doc, "original_json_path", "") or doc.metadata.get("original_json_path", ""),
                "has_full_source_text": bool(
                    getattr(doc, "has_full_source_text", False) or doc.metadata.get("has_full_source_text", False)
                ),
                "has_full_document": bool(
                    getattr(doc, "has_full_source_text", False) or doc.metadata.get("has_full_source_text", False)
                ),
                "full_source_resolver": "original_json_long_text",
                "source_type": doc.source_type,
                "document_type": doc.document_type,
                "document_title": doc.title,
                "page_number": block.page_number,
                "chunk_index": chunk_index,
                "section_title": section_title,
                "article_reference": current_article,
                "section_reference": current_section,
                "legal_reference": legal_reference,
                "block_type": block.block_type,
                "text": text,
                "embedding_text": _embedding_text(text, search_context),
            }
            chunk.update(_direct_chunk_metadata(doc.metadata))
            chunk.update(_document_chunk_metadata(doc.metadata))
            chunks.append(chunk)

    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
        chunk["total_chunks"] = total_chunks

    return chunks


def main() -> None:
    """Load and chunk every JSON-backed legal record as JSON Lines."""

    try:
        from .json_legal_documents import load_json_documents
    except ImportError:
        from json_legal_documents import load_json_documents

    documents = load_json_documents()
    if not documents:
        print("No JSON legal documents found. Check data/legal_documents or dataset.")
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
