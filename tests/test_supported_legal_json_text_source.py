from app.chunk_text import build_chunks_from_document
from app.chunking.output_json import build_chunks_from_output_json
from app.json_legal_documents import document_to_loaded_document


SUPPORTED_PAYLOAD = {
    "schema_version": "iraqi_legal_document.v2",
    "source": {
        "filename": "sample.docx",
        "extension": ".docx",
        "parser": "legal_document_parser",
        "encoding": "utf-8",
    },
    "document": {
        "title": "قرار مجلس الوزراء",
        "type": "قرار مجلس الوزراء",
        "decision_number": None,
        "year": "2024",
        "issue_date": "30/10/2024",
        "session_number": "الرابعة والاربعين",
        "session_date": "29/10/2024",
    },
    "metadata": {"text": "METADATA TEXT"},
    "references": [],
    "decision": {},
    "long_text": "PRIMARY LONG TEXT",
    "body": "BODY FALLBACK",
    "paragraphs": [{"index": 1, "text": "PARAGRAPH TEXT"}],
    "legal_entities": {},
    "extracted_fields": {},
    "signature": {},
    "extraction_notes": {},
}


def test_output_json_chunking_uses_long_text_as_primary_source():
    chunks = build_chunks_from_output_json(SUPPORTED_PAYLOAD)

    assert chunks
    assert chunks[0]["source_file"] == "sample.docx"
    assert chunks[0]["document_title"] == "قرار مجلس الوزراء"
    assert "PRIMARY LONG TEXT" in chunks[0]["text"]
    assert "BODY FALLBACK" not in chunks[0]["text"]
    assert "PARAGRAPH TEXT" not in chunks[0]["text"]


def test_json_document_adapter_uses_long_text_as_only_full_text_block():
    loaded = document_to_loaded_document(SUPPORTED_PAYLOAD)

    assert loaded.source_file == "sample.docx"
    assert loaded.title == "قرار مجلس الوزراء"
    assert len(loaded.blocks) == 1
    assert loaded.blocks[0].text == "PRIMARY LONG TEXT"


def test_generic_chunk_builder_uses_body_only_when_long_text_missing():
    payload = {**SUPPORTED_PAYLOAD, "long_text": "", "body": "BODY FALLBACK"}
    chunks = build_chunks_from_document(payload)

    assert chunks
    assert "BODY FALLBACK" in chunks[0]["text"]
    assert "PARAGRAPH TEXT" not in chunks[0]["text"]


def test_generic_chunk_builder_points_back_to_original_json_without_storing_long_text():
    payload = {
        **SUPPORTED_PAYLOAD,
        "id": "decision-json-id",
        "original_json_path": "data/output/decision-json-id.json",
    }

    chunks = build_chunks_from_document(payload)

    assert chunks[0]["document_id"] == "decision-json-id"
    assert chunks[0]["source_filename"] == "sample.docx"
    assert chunks[0]["original_json_path"] == "data/output/decision-json-id.json"
    assert chunks[0]["json_path"] == "data/output/decision-json-id.json"
    assert chunks[0]["has_full_source_text"] is True
    assert chunks[0]["has_full_document"] is True
    assert chunks[0]["full_source_resolver"] == "original_json_long_text"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["total_chunks"] == len(chunks)
    assert "long_text" not in chunks[0]
    assert "original_long_text" not in chunks[0]


def test_generic_chunk_builder_adds_structured_fields_to_embedding_text():
    payload = {
        **SUPPORTED_PAYLOAD,
        "metadata": {"subject": "diesel price adjustment"},
        "references": [{"text": "pricing reference"}],
        "legal_entities": {"organizations": ["Oil Ministry"]},
    }

    chunks = build_chunks_from_document(payload)

    assert "PRIMARY LONG TEXT" in chunks[0]["text"]
    assert "diesel price adjustment" in chunks[0]["embedding_text"]
    assert "pricing reference" in chunks[0]["embedding_text"]
    assert "Oil Ministry" in chunks[0]["embedding_text"]


def test_generic_chunk_builder_extracts_searchable_legal_metadata():
    payload = {
        **SUPPORTED_PAYLOAD,
        "long_text": (
            "بناء على كتاب وزارة النفط المرقم بالعدد (و/623) المؤرخ في 15/8/2024. "
            "توصية المجلس الوزاري للاقتصاد (24315 ق). "
            "تقرر تعديل السعر بمبلغ 400 دينار."
        ),
        "legal_entities": {"organizations": ["وزارة النفط"]},
    }

    chunks = build_chunks_from_document(payload)

    assert chunks[0]["reference_numbers"] == "و/623"
    assert chunks[0]["recommendation_numbers"] == "24315 ق"
    assert "15/8/2024" in chunks[0]["dates"]
    assert "وزارة النفط" in chunks[0]["entities"]
    assert "400 دينار" in chunks[0]["amounts"]
    assert "decision_number" not in chunks[0]


def test_generic_chunk_builder_extracts_session_date_from_session_phrase():
    payload = {
        **SUPPORTED_PAYLOAD,
        "document": {
            **SUPPORTED_PAYLOAD["document"],
            "session_date": None,
        },
        "long_text": (
            "بناء على كتاب وزارة النفط المرقم بالعدد (و/623) المؤرخ في 15/8/2024. "
            "قرر مجلس الوزراء في جلسته الاعتيادية الرابعة والأربعين المنعقدة في 29/10/2024 "
            "الموافقة على تعديل السعر."
        ),
    }

    chunks = build_chunks_from_document(payload)

    assert chunks[0]["session_date"] == "29/10/2024"
    assert chunks[0]["document_session_date"] == "29/10/2024"
    assert chunks[0]["reference_numbers"] == "و/623"
