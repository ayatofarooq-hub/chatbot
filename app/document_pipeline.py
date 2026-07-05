"""JSON-backed orchestration for document classification and fine-tuning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID, uuid4

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


class JsonDocumentRepository:
    """Minimal in-memory JSON adapter for offline document pipeline usage."""

    def __init__(self, engine=None):
        self.engine = engine

    def create_uploaded_document(self, uploaded_by: str, file_path: str, metadata: dict | None = None) -> Document:
        return {"id": 1, "uploaded_by": uploaded_by, "file_path": file_path, "status": "uploaded", "metadata": metadata or {}}

    def get_document(self, document_id: int) -> Document:
        raise LookupError("Document not found.")

    def approved_categories(self) -> list[str]:
        return []

    def pipeline_settings(self) -> dict:
        return {"learning_mode": "manual", "auto_approval_threshold": 0.0, "validation_threshold": 0.0, "scheduled_start_time": "00:00", "system_signed_in": False}

    def transition_document(self, document_id: int, *, to_status: str, actor: str, reason: str, category: str | None = None, confidence: float | None = None, classified_by: str | None = None, run_id: str | None = None, manual_override: bool = False) -> Document:
        return {"id": document_id, "status": to_status, "category": category, "reason": reason}

    def eligible_training_documents(self) -> list[Document]:
        return []

    def create_training_run(self, result: TrainingRunResult, eligible_count: int, status: str) -> None:
        return None

    def complete_training_run(self, result: TrainingRunResult, status: str) -> None:
        return None

    def mark_used_in_training(self, documents: list[Document], run_id: str, actor: str, reason: str) -> None:
        return None

    def promote_live_model(self, run_id: str, model_id: str) -> None:
        return None

    def log_event(self, event_type: str, *, actor: str, reason: str, run_id: str | None = None, document_count: int = 0) -> None:
        return None


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
