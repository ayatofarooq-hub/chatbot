from app.legal_source_text import (
    NO_USABLE_LEGAL_SOURCE_TEXT,
    reconstruct_from_paragraphs,
    source_text_from_payload,
)


def test_source_text_prefers_long_text_over_body_and_paragraphs():
    payload = {
        "long_text": "PRIMARY LONG TEXT",
        "body": "BODY FALLBACK",
        "paragraphs": [{"text": "PARAGRAPH TEXT"}],
    }

    assert source_text_from_payload(payload) == "PRIMARY LONG TEXT"


def test_source_text_uses_body_when_long_text_missing():
    payload = {
        "long_text": "",
        "body": "BODY FALLBACK",
        "paragraphs": [{"text": "PARAGRAPH TEXT"}],
    }

    assert source_text_from_payload(payload) == "BODY FALLBACK"


def test_source_text_reconstructs_from_paragraphs_only_as_last_resort():
    payload = {
        "long_text": "",
        "body": "",
        "paragraphs": [{"text": "FIRST"}, {"text": "SECOND"}],
    }

    assert source_text_from_payload(payload) == "FIRST\nSECOND"
    assert reconstruct_from_paragraphs(payload["paragraphs"]) == "FIRST\nSECOND"


def test_source_text_uses_supported_content_field():
    payload = {
        "long_text": "",
        "body": "",
        "content": "CONTENT TEXT",
        "paragraphs": [{"text": "PARAGRAPH TEXT"}],
    }

    assert source_text_from_payload(payload) == "CONTENT TEXT"


def test_source_text_uses_nested_legacy_document_text():
    payload = {
        "document": {
            "text": "NESTED DOCUMENT TEXT",
            "raw_payload": {"content": "RAW CONTENT"},
        },
    }

    assert source_text_from_payload(payload) == "NESTED DOCUMENT TEXT"


def test_source_text_uses_nested_raw_payload_content():
    payload = {
        "document": {
            "text": "",
            "raw_payload": {"content": "RAW CONTENT"},
        },
    }

    assert source_text_from_payload(payload) == "RAW CONTENT"


def test_source_text_returns_empty_when_no_usable_legal_text_exists():
    payload = {
        "schema_version": "iraqi_legal_document.v2",
        "long_text": "",
        "body": "",
        "paragraphs": [],
    }

    assert source_text_from_payload(payload) == ""
    assert NO_USABLE_LEGAL_SOURCE_TEXT == "No usable legal source text found."
