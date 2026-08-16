from app.json_builder.legal_json_schema import build_unified_legal_json
from app.json_builder.legal_output import save_legal_json


def test_build_unified_legal_json_standardizes_payload() -> None:
    document = {
        "document_type": "Cabinet Decision",
        "document_type_confidence": 0.9,
        "document_type_reason": "matched keyword",
        "metadata": {"issue_date": "2024-08-01", "ministry": "Ministry of Finance"},
        "semantic_fields": {"responsible_entities": ["Ministry"], "affected_organizations": ["Council"], "implementation_requirements": ["Submit report"], "legal_references": ["Article 5"]},
        "legal_structure": {"sections": [{"name": "decision_paragraphs", "content": "Resolved"}]},
        "original_text": "original",
        "cleaned_text": "cleaned",
    }

    payload = build_unified_legal_json(document)

    assert payload["document_classification"]["category"] == "Cabinet Decision"
    assert payload["extracted_metadata"]["issue_date"] == "2024-08-01"
    assert payload["legal_structure"]["sections"][0]["name"] == "decision_paragraphs"
    assert payload["implementation_actions"] == ["Submit report"]


def test_save_legal_json_writes_utf8_file_to_output_directory(tmp_path) -> None:
    payload = {
        "document_classification": {"category": "Cabinet Decision"},
        "extracted_metadata": {"issue_date": "2024-08-01", "decision_number": "245", "ministry": "Ministry of Defence"},
        "dates": ["2024-08-01"],
        "original_text": "text",
        "cleaned_text": "cleaned",
    }

    output_path = save_legal_json(payload, tmp_path)

    assert output_path.exists()
    assert output_path.parent == tmp_path / "legal_documents"
    assert output_path.name == "2024_cabinet_decision_245_ministry_of_defence.json"
    assert output_path.read_text(encoding="utf-8").startswith("{")
