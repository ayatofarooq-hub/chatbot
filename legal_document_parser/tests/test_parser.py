from pathlib import Path

from parser.docx_parser import DocxParser
from parser.json_builder import LegalJsonBuilder, validate_payload


ROOT = Path(__file__).resolve().parents[1]


def sample_docx() -> Path:
    files = sorted((ROOT / "input" / "docx").glob("*.docx"))
    assert files, "At least one DOCX test document must exist in input/docx."
    for path in files:
        parsed = DocxParser().parse(path)
        payload = LegalJsonBuilder().build(parsed)
        if payload["decision"]["numbered_items"] and payload["document"]["session_date"]:
            return path
    return files[0]


def build_sample_payload():
    parsed = DocxParser().parse(sample_docx())
    return parsed, LegalJsonBuilder().build(parsed)


def test_payload_uses_required_v2_structure():
    _, payload = build_sample_payload()

    assert payload["schema_version"] == "iraqi_legal_document.v2"
    assert set(
        [
            "source",
            "document",
            "metadata",
            "references",
            "decision",
            "long_text",
            "body",
            "paragraphs",
            "legal_entities",
            "extracted_fields",
            "signature",
        ]
    ).issubset(payload)
    assert payload["body"] == payload["long_text"]
    assert payload["long_text"]


def test_long_text_contains_source_derived_important_phrases():
    parsed, payload = build_sample_payload()
    important_phrases = [
        parsed.paragraphs[0],
        max(parsed.paragraphs, key=len),
        parsed.paragraphs[-1],
    ]

    for phrase in important_phrases:
        assert phrase in payload["long_text"]


def test_long_text_preserves_every_extracted_paragraph_and_item():
    parsed, payload = build_sample_payload()

    assert len(payload["paragraphs"]) == len(parsed.paragraphs)
    for paragraph in payload["paragraphs"]:
        assert paragraph["text"] in payload["long_text"]

    numbered_items = payload["decision"]["numbered_items"]
    assert numbered_items
    for item in numbered_items:
        assert item["text"] in payload["long_text"]


def test_sample_payload_validates_against_schema():
    _, payload = build_sample_payload()

    errors = validate_payload(payload, ROOT / "schemas" / "legal_document_v2.json")

    assert errors == []
    assert payload["document"]["type"]
    assert payload["document"]["year"]
    assert payload["document"]["session_date"]
