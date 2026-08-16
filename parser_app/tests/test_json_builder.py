from models.standard_schema import STANDARD_SCHEMA_VERSION, STANDARD_TOP_LEVEL_KEYS
from tests.conftest import sample_parser_json


def test_json_builder_creates_standard_schema():
    document = sample_parser_json()
    output = document.to_dict()

    assert document.schema_version == STANDARD_SCHEMA_VERSION
    assert tuple(output.keys()) == STANDARD_TOP_LEVEL_KEYS
    assert output["document"]["type"] == "Cabinet Decision"
    assert output["document"]["number"] == "245"
    assert output["document"]["year"] == "2024"
    assert output["document"]["issue_date"] == "31/12/2024"
    assert output["document"]["session"]["number"] == output["metadata"]["session_number"]
    assert output["document"]["session"]["date"] == "30/12/2024"
    assert output["document"]["title"] == document.legal_content.title
    assert output["document"]["subject"] == output["metadata"]["subject"]
    assert output["document"]["reference_number"] == "245"
    assert output["document"]["sender"] == output["metadata"]["sender"]
    assert output["document"]["recipient"] == output["metadata"]["recipient"]
    assert output["document"]["signature"] == output["metadata"]["signature"]
    assert output["document"]["attachments"] == output["metadata"]["attachments"]
    assert output["body"] == document.legal_content.body
    assert output["paragraphs"] == document.legal_content.paragraphs
    assert output["decision"]["sections"] == document.legal_content.section_items
    assert output["legal_entities"]["ministries"] == ["وزارة الصحة"]
    assert output["references"] == [
        {"type": "Decision Number", "text": "قرار مجلس الوزراء رقم 245"}
    ]
    assert output["extracted_fields"]["years"] == ["2024"]
    assert output["signature"] == {
        "text": "د. مثال - الأمين العام",
        "name": "د. مثال",
        "title": "الأمين العام",
    }
    assert output["metadata"]["document_number"] == "245"
    assert "legal_content" not in output
    assert "model_analysis" not in output
    assert "document_type" not in output
    assert "extraction" not in output
