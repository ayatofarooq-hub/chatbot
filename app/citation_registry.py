"""Persistent citation registry for auditable legal RAG answers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

try:
    from .config import CITATION_REGISTRY_FILE
    from .text_encoding import repair_json_text
except ImportError:
    from config import CITATION_REGISTRY_FILE
    from text_encoding import repair_json_text


REGISTRY_VERSION = 1


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def chunk_id_for(chunk_or_metadata: dict) -> str:
    """Return the stable chunk identifier used across Chroma and JSON files."""

    return _first_text(
        chunk_or_metadata.get("chunk_id"),
        chunk_or_metadata.get("id"),
    )


def citation_from_chunk(chunk: dict, ingest_date: str | None = None) -> dict:
    """Create the public citation object for one chunk."""

    chunk_id = chunk_id_for(chunk)
    if not chunk_id:
        raise ValueError("Chunk is missing an id/chunk_id field.")

    source_file = _first_text(chunk.get("source_file"))
    if not source_file:
        raise ValueError(f"Chunk '{chunk_id}' is missing source_file.")

    law = _first_text(
        chunk.get("law_reference"),
        chunk.get("document_title"),
        chunk.get("document_law_name"),
        chunk.get("title"),
        source_file,
    )
    article = _first_text(
        chunk.get("article"),
        chunk.get("article_reference"),
        chunk.get("legal_reference"),
        chunk.get("section_reference"),
    )

    law_number = _first_text(
        chunk.get("law_number"),
        chunk.get("document_law_number"),
    )
    law_year = _first_text(
        chunk.get("law_year"),
        chunk.get("document_law_year"),
        chunk.get("document_year"),
    )
    article_number = _first_text(
        chunk.get("article_number"),
        chunk.get("document_article_number"),
    )
    law_name = _first_text(
        chunk.get("law_name"),
        chunk.get("document_law_name"),
        chunk.get("document_title"),
        law,
    )
    legal_reference = _first_text(chunk.get("legal_reference"))
    if not legal_reference:
        reference_parts = [law_name]
        if law_number:
            reference_parts.append(f"رقم {law_number}")
        if law_year:
            reference_parts.append(f"لسنة {law_year}")
        if article_number:
            reference_parts.append(f"المادة {article_number}")
        legal_reference = " ".join(reference_parts)

    return {
        "law": law,
        "article": article,
        "law_number": law_number,
        "law_year": law_year,
        "article_number": article_number,
        "law_name": law_name,
        "legal_reference": legal_reference,
        "page_number": chunk.get("page_number", 1),
        "classification": _first_text(
            chunk.get("classification"),
            chunk.get("document_classification"),
            chunk.get("document_type"),
        ),
        "document_type": _first_text(chunk.get("document_type")),
        "source_file": source_file,
        "ingest_date": ingest_date or date.today().isoformat(),
        "chunk_id": chunk_id,
    }


def build_registry(chunks: list[dict], ingest_date: str | None = None) -> dict:
    """Build chunk and law/article lookup maps from prepared chunks."""

    by_chunk_id: dict[str, dict] = {}
    by_law_article: dict[str, dict[str, list[str]]] = {}

    for chunk in chunks:
        citation = citation_from_chunk(chunk, ingest_date=ingest_date)
        chunk_id = citation["chunk_id"]
        if chunk_id in by_chunk_id:
            raise ValueError(f"Duplicate chunk id in citation registry: {chunk_id}")

        by_chunk_id[chunk_id] = citation
        law = citation["law"] or "غير معروف"
        article = citation["article"] or "غير محدد"
        by_law_article.setdefault(law, {}).setdefault(article, []).append(chunk_id)

    return {
        "schema_version": REGISTRY_VERSION,
        "generated_at": date.today().isoformat(),
        "chunk_count": len(by_chunk_id),
        "by_chunk_id": by_chunk_id,
        "by_law_article": by_law_article,
    }


def save_registry(
    chunks: list[dict],
    registry_path: Path = CITATION_REGISTRY_FILE,
    ingest_date: str | None = None,
) -> dict:
    """Persist a complete registry for a fresh full-index build."""

    registry = build_registry(chunks, ingest_date=ingest_date)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return registry


def load_registry(registry_path: Path = CITATION_REGISTRY_FILE) -> dict:
    """Load the registry, returning an empty structure when none exists yet."""

    if not registry_path.exists():
        return {
            "schema_version": REGISTRY_VERSION,
            "generated_at": "",
            "chunk_count": 0,
            "by_chunk_id": {},
            "by_law_article": {},
        }

    data = repair_json_text(json.loads(registry_path.read_text(encoding="utf-8-sig")))
    data.setdefault("by_chunk_id", {})
    data.setdefault("by_law_article", {})
    data.setdefault("chunk_count", len(data["by_chunk_id"]))
    return data


def replace_source_citations(
    source_file: str,
    chunks: list[dict],
    registry_path: Path = CITATION_REGISTRY_FILE,
    ingest_date: str | None = None,
) -> dict:
    """Replace all registry entries for one source document."""

    registry = load_registry(registry_path)
    by_chunk_id = {
        chunk_id: citation
        for chunk_id, citation in registry["by_chunk_id"].items()
        if citation.get("source_file") != source_file
    }

    for chunk in chunks:
        citation = citation_from_chunk(chunk, ingest_date=ingest_date)
        by_chunk_id[citation["chunk_id"]] = citation

    rebuilt = build_registry_from_citations(by_chunk_id)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return rebuilt


def remove_source_citations(
    source_file: str,
    registry_path: Path = CITATION_REGISTRY_FILE,
) -> dict:
    """Delete all registry entries for one source document."""

    registry = load_registry(registry_path)
    by_chunk_id = {
        chunk_id: citation
        for chunk_id, citation in registry["by_chunk_id"].items()
        if citation.get("source_file") != source_file
    }
    rebuilt = build_registry_from_citations(by_chunk_id)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return rebuilt


def build_registry_from_citations(by_chunk_id: dict[str, dict]) -> dict:
    """Rebuild law/article lookup maps from citation records."""

    by_law_article: dict[str, dict[str, list[str]]] = {}
    for chunk_id, citation in by_chunk_id.items():
        law = _first_text(citation.get("law"), "غير معروف")
        article = _first_text(citation.get("article"), "غير محدد")
        by_law_article.setdefault(law, {}).setdefault(article, []).append(chunk_id)

    return {
        "schema_version": REGISTRY_VERSION,
        "generated_at": date.today().isoformat(),
        "chunk_count": len(by_chunk_id),
        "by_chunk_id": by_chunk_id,
        "by_law_article": by_law_article,
    }


def citations_for_metadatas(metadatas: list[dict], registry: dict | None = None) -> list[dict]:
    """Return unique structured citations for retrieved Chroma metadatas."""

    registry = registry or load_registry()
    by_chunk_id = registry.get("by_chunk_id", {})
    citations = []
    seen = set()

    for metadata in metadatas:
        chunk_id = chunk_id_for(metadata)
        if not chunk_id or chunk_id in seen:
            continue
        citation = by_chunk_id.get(chunk_id)
        if not citation:
            continue
        citations.append(citation)
        seen.add(chunk_id)

    return citations


def registry_warnings_for_metadatas(
    metadatas: list[dict],
    registry: dict | None = None,
) -> list[str]:
    """Explain which retrieved chunks are missing from the citation registry."""

    registry = registry or load_registry()
    by_chunk_id = registry.get("by_chunk_id", {})
    warnings = []

    for metadata in metadatas:
        chunk_id = chunk_id_for(metadata)
        if not chunk_id:
            warnings.append("Retrieved chunk is missing chunk_id metadata.")
        elif chunk_id not in by_chunk_id:
            warnings.append(f"Retrieved chunk '{chunk_id}' is missing from citation_registry.json.")
        else:
            citation = by_chunk_id[chunk_id]
            # Some uploaded or extracted sources do not expose a reliable year.
            # Treat law_year as optional: include it when present, but do not
            # show a user-facing warning for that field alone.
            missing = [
                field
                for field in ("law_name",)
                if not _first_text(citation.get(field))
            ]
            if missing:
                warnings.append(
                    f"Retrieved chunk '{chunk_id}' has incomplete citation metadata: "
                    + ", ".join(missing)
                    + "."
                )

    return warnings


def filter_results_to_registered(
    results: dict,
    registry: dict | None = None,
) -> tuple[dict, list[str]]:
    """Remove retrieved chunks that do not have registry-backed citations."""

    registry = registry or load_registry()
    warnings = registry_warnings_for_metadatas(
        results.get("metadatas", [[]])[0],
        registry=registry,
    )
    by_chunk_id = registry.get("by_chunk_id", {})
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    relevance_scores = results.get("relevance_scores", [[]])[0]
    bm25_scores = results.get("bm25_scores", [[]])[0]

    kept_documents = []
    kept_metadatas = []
    kept_distances = []
    kept_relevance_scores = []
    kept_bm25_scores = []

    for index, (document, metadata) in enumerate(zip(documents, metadatas)):
        chunk_id = chunk_id_for(metadata)
        if not chunk_id or chunk_id not in by_chunk_id:
            continue
        kept_documents.append(document)
        kept_metadatas.append(metadata)
        if index < len(distances):
            kept_distances.append(distances[index])
        if index < len(relevance_scores):
            kept_relevance_scores.append(relevance_scores[index])
        if index < len(bm25_scores):
            kept_bm25_scores.append(bm25_scores[index])

    filtered = dict(results)
    filtered["documents"] = [kept_documents]
    filtered["metadatas"] = [kept_metadatas]
    filtered["distances"] = [kept_distances]
    if "relevance_scores" in results:
        filtered["relevance_scores"] = [kept_relevance_scores]
    if "bm25_scores" in results:
        filtered["bm25_scores"] = [kept_bm25_scores]
    return filtered, warnings
