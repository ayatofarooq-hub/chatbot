from app.human_review import create_review_entry, decide_review, list_reviews


def test_create_review_entry_and_approve(tmp_path) -> None:
    review = create_review_entry(
        review_id="review_001",
        upload_id="upload_001",
        filename="decision.pdf",
        original_text="قرار رقم 245 لسنة 2024",
        extracted_metadata={"document_number": "245", "issue_date": "2024-08-01"},
        generated_payload={"document_classification": {"category": "Cabinet Decision"}},
        validation_status="passed",
        processing_log=[{"step": "metadata", "status": "done"}],
        review_path=tmp_path / "reviews.json",
    )

    assert review["status"] == "pending"
    assert review["review_id"] == "review_001"

    approved = decide_review(
        review["review_id"],
        decision="approve",
        reviewer="admin",
        reason="Looks correct",
        metadata={"document_number": "245"},
        review_path=tmp_path / "reviews.json",
    )

    assert approved["status"] == "approved"
    assert approved["reviewer"] == "admin"
    assert approved["metadata"]["document_number"] == "245"
    assert list_reviews(review_path=tmp_path / "reviews.json")[0]["status"] == "approved"
