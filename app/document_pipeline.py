"""Table-driven orchestration for document classification and fine-tuning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Callable, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text

from .database import create_database_engine

Document = dict


@dataclass(frozen=True)
class ClassificationDecision:
    category: str | None
    confidence: float
    reason: str = ""


@dataclass(frozen=True)
class TrainingRunResult:
    run_id: str
    model_id: str
    validation_score: float
    details: str = ""


class DocumentRepository(Protocol):
    def create_uploaded_document(
        self, uploaded_by: str, file_path: str, metadata: dict | None = None
    ) -> Document:
        ...

    def get_document(self, document_id: int) -> Document:
        ...

    def approved_categories(self) -> list[str]:
        ...

    def pipeline_settings(self) -> dict:
        ...

    def transition_document(
        self,
        document_id: int,
        *,
        to_status: str,
        actor: str,
        reason: str,
        category: str | None = None,
        confidence: float | None = None,
        classified_by: str | None = None,
        run_id: str | None = None,
        manual_override: bool = False,
    ) -> Document:
        ...

    def eligible_training_documents(self) -> list[Document]:
        ...

    def create_training_run(
        self, result: TrainingRunResult, eligible_count: int, status: str
    ) -> None:
        ...

    def complete_training_run(self, result: TrainingRunResult, status: str) -> None:
        ...

    def mark_used_in_training(
        self, documents: list[Document], run_id: str, actor: str, reason: str
    ) -> None:
        ...

    def promote_live_model(self, run_id: str, model_id: str) -> None:
        ...

    def log_event(
        self, event_type: str, *, actor: str, reason: str,
        run_id: str | None = None, document_count: int = 0
    ) -> None:
        ...


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row_dict(row) -> dict:
    return {key: _json_value(value) for key, value in row.items()}


class PostgresDocumentRepository:
    """PostgreSQL adapter for the shared documents table."""

    def __init__(self, engine=None):
        self.engine = engine or create_database_engine()
        self._own_engine = engine is None

    def close(self) -> None:
        if self._own_engine:
            self.engine.dispose()

    def create_uploaded_document(
        self, uploaded_by: str, file_path: str, metadata: dict | None = None
    ) -> Document:
        with self.engine.begin() as connection:
            row = connection.execute(text("""
                INSERT INTO public.documents (uploaded_by, file_path, status, metadata)
                VALUES (:uploaded_by, :file_path, 'uploaded', CAST(:metadata AS jsonb))
                RETURNING *
            """), {
                "uploaded_by": uploaded_by,
                "file_path": file_path,
                "metadata": json.dumps(metadata or {}),
            }).mappings().one()
            connection.execute(text("""
                INSERT INTO public.document_status_audit
                (document_id, from_status, to_status, actor, reason)
                VALUES (:id, NULL, 'uploaded', :actor, :reason)
            """), {
                "id": row["id"], "actor": uploaded_by,
                "reason": "document uploaded",
            })
            return _row_dict(row)

    def get_document(self, document_id: int) -> Document:
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT * FROM public.documents WHERE id=:id
            """), {"id": document_id}).mappings().one_or_none()
        if row is None:
            raise LookupError("Document not found.")
        return _row_dict(row)

    def approved_categories(self) -> list[str]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT source_value FROM public.document_classifications
                WHERE enabled IS TRUE AND deleted_at IS NULL
                ORDER BY display_order, id
            """)).mappings()
            return [row["source_value"] for row in rows]

    def pipeline_settings(self) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT learning_mode, auto_approval_threshold,
                       validation_threshold, scheduled_start_time,
                       system_signed_in
                FROM public.fine_tuning_settings WHERE id=1
            """)).mappings().one()
        result = _row_dict(row)
        if isinstance(result.get("scheduled_start_time"), time):
            result["scheduled_start_time"] = result["scheduled_start_time"].strftime("%H:%M")
        return result

    def transition_document(
        self,
        document_id: int,
        *,
        to_status: str,
        actor: str,
        reason: str,
        category: str | None = None,
        confidence: float | None = None,
        classified_by: str | None = None,
        run_id: str | None = None,
        manual_override: bool = False,
    ) -> Document:
        with self.engine.begin() as connection:
            current = connection.execute(text("""
                SELECT * FROM public.documents WHERE id=:id FOR UPDATE
            """), {"id": document_id}).mappings().one_or_none()
            if current is None:
                raise LookupError("Document not found.")
            row = connection.execute(text("""
                UPDATE public.documents
                SET status=:status,
                    category=CASE
                        WHEN :category_supplied THEN :category
                        ELSE category
                    END,
                    classification_confidence=COALESCE(:confidence, classification_confidence),
                    classified_by=COALESCE(:classified_by, classified_by),
                    classified_at=CASE
                        WHEN :classified_by IS NULL THEN classified_at
                        ELSE now()
                    END,
                    used_in_run_id=COALESCE(CAST(:run_id AS uuid), used_in_run_id),
                    manual_override=manual_override OR :manual_override,
                    updated_at=now()
                WHERE id=:id
                RETURNING *
            """), {
                "id": document_id, "status": to_status, "category": category,
                "category_supplied": category is not None or to_status == "unclassified",
                "confidence": confidence, "classified_by": classified_by,
                "run_id": run_id, "manual_override": manual_override,
            }).mappings().one()
            if current["status"] != to_status:
                connection.execute(text("""
                    INSERT INTO public.document_status_audit
                    (document_id, from_status, to_status, actor, reason)
                    VALUES (:id, :from_status, :to_status, :actor, :reason)
                """), {
                    "id": document_id, "from_status": current["status"],
                    "to_status": to_status, "actor": actor, "reason": reason,
                })
            return _row_dict(row)

    def eligible_training_documents(self) -> list[Document]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT * FROM public.documents
                WHERE status='approved'
                  AND used_in_run_id IS NULL
                  AND nullif(trim(category), '') IS NOT NULL
                ORDER BY uploaded_at, id
            """)).mappings()
            return [_row_dict(row) for row in rows]

    def create_training_run(
        self, result: TrainingRunResult, eligible_count: int, status: str
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO public.fine_tuning_runs
                (id, model_id, status, eligible_count, validation_score, details)
                VALUES (:id, :model_id, :status, :eligible_count, :validation_score, :details)
            """), {
                "id": str(result.run_id), "model_id": result.model_id,
                "status": status, "eligible_count": eligible_count,
                "validation_score": result.validation_score,
                "details": result.details,
            })

    def complete_training_run(self, result: TrainingRunResult, status: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                UPDATE public.fine_tuning_runs
                SET status=:status, validation_score=:validation_score,
                    details=:details, completed_at=now()
                WHERE id=:id
            """), {
                "id": str(result.run_id), "status": status,
                "validation_score": result.validation_score,
                "details": result.details,
            })

    def mark_used_in_training(
        self, documents: list[Document], run_id: str, actor: str, reason: str
    ) -> None:
        for document in documents:
            self.transition_document(
                int(document["id"]),
                to_status="used_in_training",
                actor=actor,
                reason=reason,
                run_id=run_id,
            )

    def promote_live_model(self, run_id: str, model_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                UPDATE public.fine_tuning_settings
                SET live_model_run_id=CAST(:run_id AS uuid),
                    live_model_id=:model_id,
                    updated_at=now()
                WHERE id=1
            """), {"run_id": run_id, "model_id": model_id})

    def log_event(
        self, event_type: str, *, actor: str, reason: str,
        run_id: str | None = None, document_count: int = 0
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO public.document_pipeline_events
                (event_type, actor, reason, run_id, document_count)
                VALUES (:event_type, :actor, :reason, CAST(:run_id AS uuid), :document_count)
            """), {
                "event_type": event_type, "actor": actor, "reason": reason,
                "run_id": run_id, "document_count": document_count,
            })


Classifier = Callable[[Document, list[str]], ClassificationDecision]
Trainer = Callable[[list[Document]], TrainingRunResult]


class DocumentPipeline:
    """Enforce upload, classification, approval, and scheduled training rules."""

    def __init__(self, repository: DocumentRepository):
        self.repository = repository

    def record_upload(
        self, *, uploaded_by: str, file_path: str, metadata: dict | None = None
    ) -> Document:
        return self.repository.create_uploaded_document(uploaded_by, file_path, metadata)

    def classify(self, document_id: int, classifier: Classifier) -> Document:
        document = self.repository.get_document(document_id)
        if document.get("manual_override"):
            return document

        settings = self.repository.pipeline_settings()
        if settings["learning_mode"] == "manual":
            return document

        categories = self.repository.approved_categories()
        decision = classifier(document, categories)
        reason = decision.reason or "automatic classification"
        if not decision.category or decision.category not in categories:
            return self.repository.transition_document(
                document_id,
                to_status="unclassified",
                actor="system",
                reason="automatic classification found no approved category",
                category=None,
                confidence=decision.confidence,
                classified_by="auto",
            )
        if decision.confidence < float(settings["auto_approval_threshold"]):
            return document
        return self.repository.transition_document(
            document_id,
            to_status="classified",
            actor="system",
            reason=reason,
            category=decision.category,
            confidence=decision.confidence,
            classified_by="auto",
        )

    def manual_transition(
        self,
        document_id: int,
        *,
        to_status: str,
        category: str | None,
        actor: str,
        reason: str,
    ) -> Document:
        if to_status in {"approved", "classified", "used_in_training"} and not category:
            raise ValueError("A non-empty category is required for this status.")
        if category and category not in self.repository.approved_categories():
            raise ValueError("Category must exist in the approved category list.")
        return self.repository.transition_document(
            document_id,
            to_status=to_status,
            actor=actor,
            reason=reason,
            category=category,
            manual_override=True,
        )

    def run_scheduled_fine_tuning(self, trainer: Trainer) -> dict:
        settings = self.repository.pipeline_settings()
        if not settings["system_signed_in"]:
            self.repository.log_event(
                "fine_tuning_blocked",
                actor="system",
                reason="blocked: system signed out",
            )
            return {"status": "blocked", "reason": "blocked: system signed out"}

        eligible = self.repository.eligible_training_documents()
        if not eligible:
            self.repository.log_event(
                "fine_tuning_skipped",
                actor="system",
                reason="skipped: no eligible documents",
            )
            return {"status": "skipped", "reason": "skipped: no eligible documents"}

        result = trainer(eligible)
        if not result.run_id:
            result = TrainingRunResult(str(uuid4()), result.model_id, result.validation_score, result.details)
        UUID(str(result.run_id))
        self.repository.create_training_run(result, len(eligible), "running")

        if result.validation_score < float(settings["validation_threshold"]):
            self.repository.complete_training_run(result, "failed_validation")
            self.repository.log_event(
                "fine_tuning_failed_validation",
                actor="system",
                reason="validation failed; previous live model kept",
                run_id=result.run_id,
                document_count=len(eligible),
            )
            return {"status": "failed_validation", "run_id": result.run_id}

        self.repository.mark_used_in_training(
            eligible, result.run_id, "system", "fine-tuning run completed"
        )
        self.repository.promote_live_model(result.run_id, result.model_id)
        self.repository.complete_training_run(result, "completed")
        self.repository.log_event(
            "fine_tuning_completed",
            actor="system",
            reason="new model validated and promoted",
            run_id=result.run_id,
            document_count=len(eligible),
        )
        return {
            "status": "completed",
            "run_id": result.run_id,
            "model_id": result.model_id,
            "document_count": len(eligible),
        }
