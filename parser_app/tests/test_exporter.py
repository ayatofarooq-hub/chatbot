import json

from exporters.json_exporter import JsonExporter
from tests.conftest import sample_parser_json


def test_exporter_saves_source_stem_filename(tmp_path):
    output_path = JsonExporter().save(sample_parser_json(), tmp_path)

    assert output_path.name == "document1.json"
    assert json.loads(output_path.read_text(encoding="utf-8"))["source"]["filename"] == "document1.docx"
