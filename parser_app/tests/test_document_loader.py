from pathlib import Path

import pytest

from loaders.document_loader import DocumentLoader


def test_load_txt_produces_structured_document(tmp_path: Path):
    source = tmp_path / "document1.txt"
    source.write_text("Heading\n\nParagraph one\nParagraph two", encoding="utf-8")

    document = DocumentLoader().load(source)

    assert document.filename == "document1.txt"
    assert document.extension == ".txt"
    assert document.pages == ["Heading\n\nParagraph one\nParagraph two"]
    assert document.paragraphs == ["Heading", "Paragraph one", "Paragraph two"]
    assert document.tables == []
    assert "Paragraph one" in document.raw_text


def test_load_html_extracts_visible_text(tmp_path: Path):
    source = tmp_path / "document1.html"
    source.write_text("<h1>Title</h1><p>Body text</p>", encoding="utf-8")

    document = DocumentLoader().load(source)

    assert document.paragraphs == ["Title", "Body text"]


def test_loader_rejects_unsupported_extension(tmp_path: Path):
    source = tmp_path / "document1.exe"
    source.write_text("not supported", encoding="utf-8")

    with pytest.raises(ValueError):
        DocumentLoader().load(source)
