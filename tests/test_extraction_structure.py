from pathlib import Path

from app.extraction.document_loader import load_document


def test_load_document_preserves_structure_from_html(tmp_path: Path) -> None:
    html_path = tmp_path / "sample.html"
    html_path.write_text(
        "<html><body><h1>Title</h1><p>Intro</p><ul><li>One</li><li>Two</li></ul><table><tr><th>Col</th><th>Value</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>",
        encoding="utf-8",
    )

    document = load_document(html_path)
    payload = document.to_payload()

    assert document.title == "Title"
    assert any(block["type"] == "heading" for block in document.blocks)
    assert any(block["type"] == "paragraph" for block in document.blocks)
    assert any(block["type"] == "list" for block in document.blocks)
    assert any(block["type"] == "table" for block in document.blocks)
    assert payload["document"] == "Title"
    assert payload["paragraphs"]
    assert payload["tables"]
