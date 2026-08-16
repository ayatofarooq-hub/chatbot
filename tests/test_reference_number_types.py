from pathlib import Path

from app.rag_answer import MISSING_DECISION_NUMBER_ANSWER, decision_number_answer
from legal_rag.grounded_answer import answer_decision_number_if_known
from legal_document_parser.parser.docx_parser import ParsedDocx
from legal_document_parser.parser.json_builder import LegalJsonBuilder
from legal_document_parser.parser.reference_extractor import ReferenceExtractor


def test_recommendation_number_is_typed_reference_not_decision_number() -> None:
    text = (
        "\u0625\u0642\u0631\u0627\u0631 \u062a\u0648\u0635\u064a\u0629 "
        "\u0627\u0644\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0627\u0631\u064a "
        "\u0644\u0644\u0627\u0642\u062a\u0635\u0627\u062f (24315 \u0642)"
    )

    references = ReferenceExtractor().extract(text)

    assert {"type": "recommendation_number", "text": "24315 \u0642"} in references
    assert not any(reference.get("type") == "decision_number" for reference in references)


def test_book_number_is_reference_number_not_decision_number() -> None:
    text = (
        "\u0643\u062a\u0627\u0628 \u0648\u0632\u0627\u0631\u0629 "
        "\u0627\u0644\u0646\u0641\u0637 \u0628\u0627\u0644\u0639\u062f\u062f "
        "(\u0648/623)"
    )

    references = ReferenceExtractor().extract(text)

    assert {"type": "reference_number", "text": "\u0648/623"} in references
    assert not any(reference.get("type") == "decision_number" for reference in references)


def test_json_builder_keeps_typed_numbers_out_of_decision_number() -> None:
    paragraphs = [
        "\u0642\u0631\u0627\u0631 \u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
        (
            "\u0625\u0642\u0631\u0627\u0631 \u062a\u0648\u0635\u064a\u0629 "
            "\u0627\u0644\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0627\u0631\u064a "
            "\u0644\u0644\u0627\u0642\u062a\u0635\u0627\u062f (24315 \u0642)"
        ),
        (
            "\u0643\u062a\u0627\u0628 \u0648\u0632\u0627\u0631\u0629 "
            "\u0627\u0644\u0646\u0641\u0637 \u0628\u0627\u0644\u0639\u062f\u062f "
            "(\u0648/623)"
        ),
    ]
    parsed = ParsedDocx(
        source_path=Path("sample.docx"),
        filename="sample.docx",
        paragraphs=paragraphs,
        tables=[],
        full_text="\n".join(paragraphs),
    )

    payload = LegalJsonBuilder().build(parsed)

    assert payload["document"]["decision_number"] is None
    assert payload["extracted_fields"]["recommendation_numbers"] == ["24315 \u0642"]
    assert payload["extracted_fields"]["reference_numbers"] == ["\u0648/623"]


def test_decision_number_answer_ignores_document_and_reference_numbers() -> None:
    results = {
        "documents": [["text"]],
        "metadatas": [
            [
                {
                    "document_number": "\u0648/623",
                    "reference_numbers": "24315 \u0642",
                    "recommendation_numbers": "24315 \u0642",
                }
            ]
        ],
    }

    answer = decision_number_answer("\u0645\u0627 \u0631\u0642\u0645 \u0627\u0644\u0642\u0631\u0627\u0631\u061f", results)

    assert answer is not None
    assert answer.content == MISSING_DECISION_NUMBER_ANSWER


def test_grounded_decision_number_answer_ignores_document_number() -> None:
    results = {
        "documents": [["text"]],
        "metadatas": [[{"document_number": "\u0648/623", "reference_numbers": "24315 \u0642"}]],
    }

    answer = answer_decision_number_if_known(
        "\u0645\u0627 \u0631\u0642\u0645 \u0627\u0644\u0642\u0631\u0627\u0631\u061f",
        results,
    )

    assert answer is not None
    assert answer["answer"] == MISSING_DECISION_NUMBER_ANSWER
