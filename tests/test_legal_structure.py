from app.classifiers.legal_structure import extract_legal_structure


def test_extract_legal_structure_for_cabinet_decision() -> None:
    text = """
    We base this on the Constitution.
    The decision hereby resolves to appoint a committee.
    1. Appoint the committee.
    - The committee will report.
    Article 5 of the law shall apply.
    The ministry shall implement this.
    Except where otherwise stated.
    """

    structure = extract_legal_structure("Cabinet Decision", text)

    assert any(section["name"] == "decision_paragraphs" for section in structure["sections"])
    assert any(section["name"] == "numbered_items" for section in structure["sections"])
    assert any(section["name"] == "exceptions" for section in structure["sections"])
