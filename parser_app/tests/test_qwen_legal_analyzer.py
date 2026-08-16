from extractors.qwen_legal_analyzer import QwenLegalAnalyzer
from models.document import CleanedDocument
from tests.conftest import sample_document_type, sample_metadata


class FakeClient:
    def generate_json(self, prompt: str) -> str:
        assert "Fill only these requested fields" in prompt
        return """
        {
          "legal_meaning": "meaning",
          "legal_entities": [{"name": "وزارة الصحة", "type": "ministry", "role": "sender"}],
          "structured_fields": {"legal_objective": "objective"},
          "summary": "summary"
        }
        """


def test_qwen_analyzer_uses_client_and_returns_structured_analysis():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=["نص"],
        tables=[],
        raw_text="نص",
    )

    analysis = QwenLegalAnalyzer(FakeClient()).analyze(
        document,
        sample_metadata(),
        sample_document_type(),
        requested_fields=["legal_objective"],
    )

    assert analysis.legal_meaning == "meaning"
    assert analysis.legal_entities[0]["name"] == "وزارة الصحة"
    assert analysis.structured_fields["legal_objective"] == "objective"
