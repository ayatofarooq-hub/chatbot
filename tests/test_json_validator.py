from app.json_builder.json_validator import validate_legal_json


def test_validate_legal_json_detects_missing_required_fields() -> None:
    payload = {
        "document_classification": {"category": "Cabinet Decision"},
        "extracted_metadata": {"issue_date": "2024-08-01"},
        "legal_structure": {"sections": [{"name": "decision_paragraphs", "content": "Resolved"}]},
        "dates": ["2024-08-01"],
        "cleaned_text": "cleaned",
        "original_text": "original",
    }

    is_valid, errors = validate_legal_json(payload)

    assert is_valid is True
    assert errors == []
