"""Structured retrieval logging for legal RAG diagnostics."""

from __future__ import annotations

import logging
from typing import Any


LOGGER_NAME = "legal_rag.retrieval"
logger = logging.getLogger(LOGGER_NAME)


def _first(values: list[Any], index: int, default: Any = "") -> Any:
    return values[index] if index < len(values) else default


def _source_label(metadata: dict[str, Any]) -> str:
    return str(
        metadata.get("source_filename")
        or metadata.get("source_file")
        or metadata.get("filename")
        or metadata.get("document_title")
        or metadata.get("title")
        or "unknown"
    )


def log_retrieval_results(question: str, results: dict[str, Any]) -> None:
    """Log retrieved documents and scores after reranking."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    scores = results.get("relevance_scores", [[]])[0] or results.get("distances", [[]])[0]
    logger.info("[RETRIEVAL]\nQuestion: %s", question)
    if not metadatas:
        logger.info("[RETRIEVED DOCUMENTS]\nNone")
        logger.info("[SELECTED DOCUMENT]\nNone")
        return

    labels = [_source_label(metadata) for metadata in metadatas if isinstance(metadata, dict)]
    logger.info("[RETRIEVED DOCUMENTS]\n%s", "\n".join(labels))
    logger.info(
        "[DOCUMENT SCORES]\n%s",
        "\n".join(
            f"{_source_label(metadata)}: {_first(scores, index, 'missing')}"
            for index, metadata in enumerate(metadatas)
            if isinstance(metadata, dict)
        ),
    )
    top_metadata = metadatas[0] if isinstance(metadatas[0], dict) else {}
    logger.info("[SELECTED DOCUMENT]\n%s", _source_label(top_metadata))
    logger.info("[SCORE]\n%s", _first(scores, 0, "missing"))
    json_file = top_metadata.get("json_path") or top_metadata.get("original_json_path") or "missing"
    logger.info("[JSON FILE]\n%s", json_file)


def log_long_text_status(metadata: dict[str, Any], found: bool, context_status: str, context_length: int) -> None:
    """Log source JSON and full-text availability for answer context."""

    json_file = metadata.get("json_path") or metadata.get("original_json_path") or "missing"
    logger.info("[JSON FILE]\n%s", json_file)
    logger.info("[LONG_TEXT]\nFound: %s", str(bool(found)).lower())
    logger.info("[CONTEXT]\n%s\nLength: %s", context_status, context_length)


def log_answer_generation(stage: str) -> None:
    """Log answer-generation stage transitions."""

    logger.info("[ANSWER GENERATION]\n%s", stage)
