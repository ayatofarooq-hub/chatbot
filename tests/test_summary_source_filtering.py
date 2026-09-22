import json

from app.chunk_text import build_chunks_from_document
from backend.services import json_repository as repository_module
from backend.services.json_repository import JsonRepository


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_chunk_builder_excludes_summary_explanation_lines():
    payload = {
        "id": "decision-1",
        "source": {"filename": "decision-1.docx"},
        "document": {"title": "قرار مجلس الوزراء", "type": "قرار"},
        "long_text": (
            "الشرح التفصيلي: هذا ملخص مولد وليس مصدرا أصليا.\n"
            "قرر مجلس الوزراء في جلسته المنعقدة في 29/10/2024 الموافقة على الطلب."
        ),
    }

    chunks = build_chunks_from_document(payload)

    assert chunks
    assert "الشرح التفصيلي" not in chunks[0]["text"]
    assert "ملخص مولد" not in chunks[0]["text"]
    assert "قرر مجلس الوزراء" in chunks[0]["text"]


def test_repository_prefers_output_roots_and_skips_summary_dataset_decisions(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    parser_root = tmp_path / "legal_document_parser" / "output" / "json"
    data_output_root = data_root / "output"
    dataset_root = tmp_path / "dataset"

    monkeypatch.setattr(repository_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(repository_module, "SEED_DATASET_ROOT", dataset_root)
    monkeypatch.setattr(
        repository_module,
        "PREFERRED_OUTPUT_ROOTS",
        (parser_root, data_output_root),
    )

    _write_json(parser_root / "parser.json", {"id": "parser-doc", "long_text": "نص أصلي"})
    _write_json(data_output_root / "output.json", {"id": "output-doc", "long_text": "نص أصلي"})
    _write_json(dataset_root / "laws" / "law.json", {"id": "law-doc", "long_text": "نص أصلي"})
    _write_json(
        dataset_root / "decisions" / "summary.json",
        {
            "id": "summary-decision",
            "content": "العنوان: قرار\nالشرح التفصيلي: هذا وصف مولد فقط.",
        },
    )

    documents = JsonRepository(data_root=data_root).list_documents()
    document_ids = [document["id"] for document in documents]

    assert "parser-doc" in document_ids
    assert "output-doc" in document_ids
    assert "law-doc" in document_ids
    assert "summary-decision" not in document_ids
    assert documents[0]["id"] == "parser-doc"
    assert documents[1]["id"] == "output-doc"
    assert documents[0]["original_json_path"] == "legal_document_parser\\output\\json\\parser.json"
