"""Simple admin review workflow for uploaded legal documents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.json_storage import read_json, write_json

DEFAULT_REVIEW_PATH = Path("data/legal_documents/reviews.json")


def _review_path(review_path: str | Path | None = None) -> Path:
    return Path(review_path or DEFAULT_REVIEW_PATH)


def create_review_entry(
    *,
    review_id: str,
    upload_id: str,
    filename: str,
    original_text: str,
    extracted_metadata: dict[str, Any],
    generated_payload: dict[str, Any],
    validation_status: str,
    processing_log: list[dict[str, Any]],
    review_path: str | Path | None = None,
) -> dict[str, Any]:
    path = _review_path(review_path)
    reviews = read_json(path, [])
    if not isinstance(reviews, list):
        reviews = []
    entry = {
        "review_id": review_id,
        "upload_id": upload_id,
        "filename": filename,
        "original_text": original_text,
        "extracted_metadata": extracted_metadata,
        "generated_payload": generated_payload,
        "validation_status": validation_status,
        "processing_log": processing_log,
        "status": "pending",
        "reviewer": None,
        "reason": None,
        "metadata": dict(extracted_metadata),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reviews.append(entry)
    write_json(path, reviews)
    return entry


def list_reviews(*, review_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = _review_path(review_path)
    reviews = read_json(path, [])
    return reviews if isinstance(reviews, list) else []


def decide_review(
    review_id: str,
    *,
    decision: str,
    reviewer: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
    review_path: str | Path | None = None,
) -> dict[str, Any]:
    path = _review_path(review_path)
    reviews = read_json(path, [])
    if not isinstance(reviews, list):
        reviews = []
    for review in reviews:
        if review.get("review_id") != review_id:
            continue
        review["status"] = "approved" if decision == "approve" else "rejected"
        review["reviewer"] = reviewer
        review["reason"] = reason
        review["metadata"] = {**review.get("metadata", {}), **(metadata or {})}
        review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(path, reviews)
        if decision == "approve":
            from .uploaded_documents import index_reviewed_document

            index_reviewed_document(review)
        return review
    raise LookupError(f"Review '{review_id}' not found")
