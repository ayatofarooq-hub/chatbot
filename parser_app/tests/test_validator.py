import json

import pytest

from validators.validation_engine import ValidationEngine, ValidationError
from tests.conftest import sample_parser_json


def test_validation_engine_accepts_standard_json_file(tmp_path):
    path = tmp_path / "document1.json"
    path.write_text(json.dumps(sample_parser_json().to_dict(), ensure_ascii=False), encoding="utf-8")

    parsed = ValidationEngine().validate_file(path)

    assert parsed["schema_version"] == "iraqi_legal_document.v2"


def test_validation_engine_rejects_invalid_date():
    document = sample_parser_json().to_dict()
    document["metadata"]["issue_date"] = "31-12-2024"

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_banned_embedding_field():
    document = sample_parser_json().to_dict()
    document["embedding"] = [0.1, 0.2]

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_shortened_item_text():
    document = sample_parser_json().to_dict()
    document["decision"]["sections"][0]["text"] = ""

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_invalid_section_arrays():
    document = sample_parser_json().to_dict()
    document["decision"]["sections"][0]["entities"] = None

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_body_mismatch():
    document = sample_parser_json().to_dict()
    document["body"] = ""

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_paragraph_mismatch():
    document = sample_parser_json().to_dict()
    document["paragraphs"] = []

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_invalid_decision_sections():
    document = sample_parser_json().to_dict()
    document["decision"]["sections"] = {}

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_legal_entities_mismatch():
    document = sample_parser_json().to_dict()
    document["legal_entities"] = {}

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_references_mismatch():
    document = sample_parser_json().to_dict()
    document["references"] = {}

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)


def test_validation_engine_rejects_extracted_fields_mismatch():
    document = sample_parser_json().to_dict()
    document["extracted_fields"] = {}

    with pytest.raises(ValidationError):
        ValidationEngine().validate_dict(document)
