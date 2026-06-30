"""Unit tests for table-driven document pipeline orchestration."""

import unittest

from app.document_pipeline import (
    ClassificationDecision,
    DocumentPipeline,
    TrainingRunResult,
)


class FakeRepository:
    def __init__(self):
        self.documents = {}
        self.categories = ["civil", "criminal"]
        self.settings = {
            "learning_mode": "manual",
            "auto_approval_threshold": 0.8,
            "validation_threshold": 0.75,
            "scheduled_start_time": "02:00",
            "system_signed_in": True,
        }
        self.audit = []
        self.events = []
        self.promoted = None
        self.runs = []

    def create_uploaded_document(self, uploaded_by, file_path, metadata=None):
        document_id = len(self.documents) + 1
        document = {
            "id": document_id,
            "uploaded_by": uploaded_by,
            "file_path": file_path,
            "status": "uploaded",
            "category": None,
            "used_in_run_id": None,
            "manual_override": False,
            "metadata": metadata or {},
        }
        self.documents[document_id] = document
        self.audit.append((document_id, None, "uploaded", uploaded_by, "document uploaded"))
        return document.copy()

    def get_document(self, document_id):
        return self.documents[document_id].copy()

    def approved_categories(self):
        return list(self.categories)

    def pipeline_settings(self):
        return self.settings.copy()

    def transition_document(
        self, document_id, *, to_status, actor, reason, category=None,
        confidence=None, classified_by=None, run_id=None, manual_override=False
    ):
        document = self.documents[document_id]
        previous = document["status"]
        document["status"] = to_status
        if category is not None or to_status == "unclassified":
            document["category"] = category
        if confidence is not None:
            document["classification_confidence"] = confidence
        if classified_by:
            document["classified_by"] = classified_by
        if run_id:
            document["used_in_run_id"] = run_id
        document["manual_override"] = document["manual_override"] or manual_override
        if previous != to_status:
            self.audit.append((document_id, previous, to_status, actor, reason))
        return document.copy()

    def eligible_training_documents(self):
        return [
            document.copy()
            for document in self.documents.values()
            if document["status"] == "approved"
            and document["category"]
            and not document["used_in_run_id"]
        ]

    def create_training_run(self, result, eligible_count, status):
        self.runs.append((result.run_id, eligible_count, status))

    def complete_training_run(self, result, status):
        self.runs.append((result.run_id, status))

    def mark_used_in_training(self, documents, run_id, actor, reason):
        for document in documents:
            self.transition_document(
                document["id"],
                to_status="used_in_training",
                actor=actor,
                reason=reason,
                run_id=run_id,
            )

    def promote_live_model(self, run_id, model_id):
        self.promoted = (run_id, model_id)

    def log_event(self, event_type, *, actor, reason, run_id=None, document_count=0):
        self.events.append((event_type, actor, reason, run_id, document_count))


class DocumentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.pipeline = DocumentPipeline(self.repo)

    def test_record_upload_creates_uploaded_document_without_category(self):
        document = self.pipeline.record_upload(
            uploaded_by="user-1", file_path="/uploads/law.pdf"
        )
        self.assertEqual(document["status"], "uploaded")
        self.assertIsNone(document["category"])

    def test_manual_learning_mode_never_auto_advances(self):
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        classified = self.pipeline.classify(
            document["id"],
            lambda _document, _categories: ClassificationDecision("civil", 0.99),
        )
        self.assertEqual(classified["status"], "uploaded")

    def test_automatic_mode_classifies_only_above_threshold(self):
        self.repo.settings["learning_mode"] = "automatic"
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        classified = self.pipeline.classify(
            document["id"],
            lambda _document, categories: ClassificationDecision(categories[0], 0.95),
        )
        self.assertEqual(classified["status"], "classified")
        self.assertEqual(classified["category"], "civil")
        self.assertEqual(classified["classified_by"], "auto")

    def test_low_confidence_stays_uploaded(self):
        self.repo.settings["learning_mode"] = "automatic"
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        classified = self.pipeline.classify(
            document["id"],
            lambda _document, _categories: ClassificationDecision("civil", 0.40),
        )
        self.assertEqual(classified["status"], "uploaded")

    def test_unknown_category_becomes_unclassified(self):
        self.repo.settings["learning_mode"] = "automatic"
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        classified = self.pipeline.classify(
            document["id"],
            lambda _document, _categories: ClassificationDecision("invented", 0.99),
        )
        self.assertEqual(classified["status"], "unclassified")
        self.assertIsNone(classified["category"])

    def test_manual_override_prevents_later_auto_reversal(self):
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        approved = self.pipeline.manual_transition(
            document["id"],
            to_status="approved",
            category="civil",
            actor="admin-1",
            reason="admin approved",
        )
        self.repo.settings["learning_mode"] = "automatic"
        after_auto = self.pipeline.classify(
            approved["id"],
            lambda _document, _categories: ClassificationDecision("criminal", 1.0),
        )
        self.assertEqual(after_auto["status"], "approved")
        self.assertEqual(after_auto["category"], "civil")

    def test_signed_out_scheduled_job_is_blocked(self):
        self.repo.settings["system_signed_in"] = False
        result = self.pipeline.run_scheduled_fine_tuning(lambda _documents: None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.repo.events[0][2], "blocked: system signed out")

    def test_scheduled_job_skips_empty_eligible_set(self):
        result = self.pipeline.run_scheduled_fine_tuning(lambda _documents: None)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(self.repo.events[0][2], "skipped: no eligible documents")

    def test_validation_failure_keeps_documents_approved_and_model_unpromoted(self):
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        self.pipeline.manual_transition(
            document["id"],
            to_status="approved",
            category="civil",
            actor="admin-1",
            reason="admin approved",
        )
        result = self.pipeline.run_scheduled_fine_tuning(
            lambda _documents: TrainingRunResult("00000000-0000-0000-0000-000000000001", "model-a", 0.3)
        )
        self.assertEqual(result["status"], "failed_validation")
        self.assertEqual(self.repo.documents[document["id"]]["status"], "approved")
        self.assertIsNone(self.repo.promoted)

    def test_successful_training_marks_documents_and_promotes_model(self):
        document = self.pipeline.record_upload(uploaded_by="user-1", file_path="a.pdf")
        self.pipeline.manual_transition(
            document["id"],
            to_status="approved",
            category="civil",
            actor="admin-1",
            reason="admin approved",
        )
        result = self.pipeline.run_scheduled_fine_tuning(
            lambda _documents: TrainingRunResult("00000000-0000-0000-0000-000000000002", "model-b", 0.9)
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.repo.documents[document["id"]]["status"], "used_in_training")
        self.assertEqual(self.repo.documents[document["id"]]["used_in_run_id"], result["run_id"])
        self.assertEqual(self.repo.promoted, (result["run_id"], "model-b"))


if __name__ == "__main__":
    unittest.main()
