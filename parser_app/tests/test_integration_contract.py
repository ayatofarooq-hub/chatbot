from models.standard_schema import (
    STANDARD_SCHEMA_VERSION,
    STANDARD_TOP_LEVEL_KEYS,
    find_banned_keys,
)
from tests.conftest import sample_parser_json


def test_parser_contract_json_is_utf8_self_contained_and_standard():
    document = sample_parser_json().to_dict()
    encoded = document.__repr__().encode("utf-8")

    assert encoded.decode("utf-8")
    assert document["schema_version"] == STANDARD_SCHEMA_VERSION
    assert tuple(document.keys()) == STANDARD_TOP_LEVEL_KEYS
    assert find_banned_keys(document) == []
    assert document["body"]
    assert document["source"]["filename"]
    assert "legal_content" not in document
    assert "model_analysis" not in document


def test_contract_document_states_no_integration():
    contract_text = open("INTEGRATION_CONTRACT.md", encoding="utf-8").read()

    assert "No integration is implemented" in contract_text
    assert "The only contract boundary is the filesystem JSON output" in contract_text
    assert "It never parses DOCX" in contract_text
