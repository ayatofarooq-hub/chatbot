from app.classifiers.document_type import classify_document_type, SUPPORTED_CATEGORIES


def test_classify_document_type_detects_known_categories() -> None:
    category, confidence, reason = classify_document_type("Cabinet Decision regarding the formation of a committee", SUPPORTED_CATEGORIES)

    assert category == "Cabinet Decision"
    assert confidence > 0.0
    assert reason
