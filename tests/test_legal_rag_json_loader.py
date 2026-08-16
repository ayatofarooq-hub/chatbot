from pathlib import Path

from legal_rag.json_loader import load_legal_json_documents
from legal_rag.json_loader import load_legal_json_file
from legal_rag.legal_chunker import build_chunks_from_documents


ROOT = Path(__file__).resolve().parents[1]
LEGAL_JSON_DIR = ROOT / "legal_document_parser" / "output" / "json"


def test_loader_reads_generated_legal_json_fields():
    documents = load_legal_json_documents(LEGAL_JSON_DIR)

    assert documents
    first = documents[0]
    assert first.long_text
    assert first.document
    assert first.sections
    assert isinstance(first.legal_items, list)
    assert isinstance(first.references, list)
    assert isinstance(first.entities, dict)


def test_loader_prefers_long_text_and_uses_body_only_as_fallback(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(
        """{
          "schema_version": "iraqi_legal_document.v2",
          "source": {"filename": "sample.docx"},
          "document": {"title": "title", "year": "2024"},
          "metadata": {},
          "decision": {},
          "long_text": "PRIMARY LONG TEXT",
          "body": "BODY FALLBACK",
          "paragraphs": [{"index": 1, "text": "PARAGRAPH TEXT"}],
          "references": [],
          "legal_entities": {}
        }""",
        encoding="utf-8",
    )

    loaded = load_legal_json_file(path)

    assert loaded.long_text == "PRIMARY LONG TEXT"

    path.write_text(
        """{
          "schema_version": "iraqi_legal_document.v2",
          "source": {"filename": "sample.docx"},
          "document": {"title": "title", "year": "2024"},
          "metadata": {},
          "decision": {},
          "long_text": "",
          "body": "BODY FALLBACK",
          "paragraphs": [{"index": 1, "text": "PARAGRAPH TEXT"}],
          "references": [],
          "legal_entities": {}
        }""",
        encoding="utf-8",
    )

    loaded = load_legal_json_file(path)

    assert loaded.long_text == "BODY FALLBACK"


def test_loader_creates_document_search_record(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(
        """{
          "schema_version": "iraqi_legal_document.v2",
          "source": {"filename": "sample.docx"},
          "document": {
            "title": "Cabinet decision",
            "type": "Cabinet Decision",
            "decision_number": null,
            "year": "2024",
            "issue_date": "30/10/2024",
            "session_number": "forty fourth",
            "session_date": "29/10/2024"
          },
          "metadata": {"subject": "fuel prices"},
          "decision": {},
          "long_text": "full legal text about diesel",
          "body": "fallback body",
          "paragraphs": [],
          "references": [{"text": "pricing recommendation"}],
          "legal_entities": {"organizations": ["Oil Ministry"], "companies": [], "persons": [], "all": []},
          "extracted_fields": {"numeric_values": ["400"]}
        }""",
        encoding="utf-8",
    )

    loaded = load_legal_json_file(path)
    record = loaded.search_record

    assert record.document_id == loaded.document_id
    assert record.filename == "sample.docx"
    assert record.title == "Cabinet decision"
    assert record.document_type == "Cabinet Decision"
    assert record.decision_number is None
    assert record.year == "2024"
    assert record.issue_date == "30/10/2024"
    assert record.session_number == "forty fourth"
    assert record.session_date == "29/10/2024"
    assert record.references == [{"text": "pricing recommendation"}]
    assert "Oil Ministry" in record.entities
    assert record.long_text == "full legal text about diesel"
    for value in (
        "Cabinet decision",
        "Cabinet Decision",
        "2024",
        "30/10/2024",
        "forty fourth",
        "29/10/2024",
        "pricing recommendation",
        "Oil Ministry",
        "400",
        "full legal text about diesel",
    ):
        assert value in record.search_text


def test_chunker_preserves_traceable_metadata_for_every_chunk():
    documents = load_legal_json_documents(LEGAL_JSON_DIR)
    chunks = build_chunks_from_documents(documents)

    assert chunks
    required = {
        "chunk_id",
        "document_id",
        "source_filename",
        "original_json_path",
        "json_path",
        "has_full_source_text",
        "has_full_document",
        "full_source_resolver",
        "document_type",
        "document_number",
        "year",
        "issue_date",
        "session_number",
        "session_date",
        "title",
        "subject",
        "section",
        "item_number",
        "source_file",
        "total_chunks",
        "reference_numbers",
        "text",
    }
    chunks_per_document = {}
    for chunk in chunks:
        chunks_per_document[chunk["document_id"]] = chunks_per_document.get(chunk["document_id"], 0) + 1
    for chunk in chunks:
        assert required.issubset(chunk)
        assert chunk["chunk_id"] == chunk["id"]
        assert chunk["text"]
        assert chunk["source_filename"] == chunk["source_file"]
        assert chunk["original_json_path"].endswith(".json")
        assert chunk["json_path"] == chunk["original_json_path"]
        assert chunk["has_full_source_text"] is True
        assert chunk["has_full_document"] is True
        assert chunk["full_source_resolver"] == "original_json_long_text"
        assert chunk["total_chunks"] == chunks_per_document[chunk["document_id"]]
        assert "long_text" not in chunk
        assert "original_long_text" not in chunk
        assert chunk["metadata"]["chunk_id"] == chunk["chunk_id"]
        assert chunk["metadata"]["document_id"] == chunk["document_id"]
        assert chunk["metadata"]["source_filename"] == chunk["source_filename"]
        assert chunk["metadata"]["chunk_index"] == chunk["chunk_index"]
        assert chunk["metadata"]["total_chunks"] == chunks_per_document[chunk["document_id"]]
        assert chunk["metadata"]["json_path"] == chunk["json_path"]
        assert chunk["metadata"]["has_full_document"] is True


def test_oil_contract_amount_is_in_one_traceable_legal_chunk():
    documents = load_legal_json_documents(LEGAL_JSON_DIR)
    chunks = build_chunks_from_documents(documents)

    matching = [
        chunk
        for chunk in chunks
        if "شركة نفط البصرة" in chunk["text"]
        and "شركة المشاريع النفطية" in chunk["text"]
        and "4.594.000.050" in chunk["text"]
    ]

    assert matching
    chunk = matching[0]
    assert chunk["source_file"].endswith(".docx")
    assert chunk["document_id"]
    assert chunk["section"]
    assert chunk["item_number"]
    assert chunk["chunk_id"]


def test_fuel_oil_price_line_is_in_traceable_legal_chunk():
    documents = load_legal_json_documents(LEGAL_JSON_DIR)
    chunks = build_chunks_from_documents(documents)

    matching = [
        chunk
        for chunk in chunks
        if "منتوج زيت الوقود" in chunk["text"]
        and "150.000" in chunk["text"]
        and "350.000" in chunk["text"]
    ]

    assert matching
    chunk = matching[0]
    assert chunk["source_file"] == "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx"
    assert chunk["document_id"]
    assert chunk["json_path"].endswith("قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.json")


def test_chunker_adds_metadata_entities_and_references_to_embedding_text(tmp_path):
    path = tmp_path / "decision.json"
    path.write_text(
        """{
          "schema_version": "iraqi_legal_document.v2",
          "source": {"filename": "opaque.docx"},
          "document": {"title": "Fuel decision", "type": "Decision", "year": "2024"},
          "metadata": {"subject": "diesel price adjustment"},
          "decision": {"sections": [{"section_id": "body", "title": "Body", "text": "Legal body"}], "numbered_items": []},
          "long_text": "Legal body",
          "body": "Legal body",
          "paragraphs": [{"index": 1, "text": "Legal body"}],
          "references": [{"text": "pricing reference"}],
          "legal_entities": {"organizations": ["Oil Ministry"], "companies": [], "persons": [], "all": []}
        }""",
        encoding="utf-8",
    )

    chunks = build_chunks_from_documents([load_legal_json_file(path)])

    assert chunks
    assert chunks[0]["text"] == "Legal body"
    assert "diesel price adjustment" in chunks[0]["embedding_text"]
    assert "pricing reference" in chunks[0]["embedding_text"]
    assert "Oil Ministry" in chunks[0]["embedding_text"]
