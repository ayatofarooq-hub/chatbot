from app.classifiers.document_cleaner import clean_document_text


def test_clean_document_text_removes_artifacts_but_preserves_structure() -> None:
    text = """
    Page 1
    Ministry of Finance
    Cabinet Decision No. 123/2024
    
    Article 1. The Ministry shall act.
    - bullet one
    - bullet two
    
    2024-08-01
    
    Page 2
    Ministry of Finance
    Cabinet Decision No. 123/2024
    """

    cleaned = clean_document_text(text)

    assert "Page 1" not in cleaned
    assert "Page 2" not in cleaned
    assert "Cabinet Decision No. 123/2024" in cleaned
    assert "Article 1. The Ministry shall act." in cleaned
    assert "- bullet one" in cleaned
    assert "2024-08-01" in cleaned
