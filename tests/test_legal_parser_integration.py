from unittest.mock import patch

from app.legal_parser_integration import rebuild_legal_parser_index


@patch("app.legal_parser_integration.index_legal_parser_json_outputs")
@patch("app.legal_parser_integration.parse_legal_parser_docx_files")
def test_rebuild_legal_parser_index_parses_then_indexes(mock_parse, mock_index):
    mock_parse.return_value = [
        {
            "input_file": "decision.docx",
            "generated_json_file": "decision.json",
            "validation_errors": [],
        },
        {
            "input_file": "other.docx",
            "generated_json_file": "other.json",
            "validation_errors": ["decision.sections must exist"],
        },
    ]
    mock_index.return_value = {
        "documents": 2,
        "chunks": 4,
        "collection": "iraqi_legal_documents",
    }

    result = rebuild_legal_parser_index(parse_docx=True)

    mock_parse.assert_called_once_with()
    mock_index.assert_called_once_with()
    assert result["parsed_documents"] == 2
    assert result["parser_validation_errors"] == 1
    assert result["index"]["chunks"] == 4


@patch("app.legal_parser_integration.index_legal_parser_json_outputs")
@patch("app.legal_parser_integration.parse_legal_parser_docx_files")
def test_rebuild_legal_parser_index_can_skip_docx_parse(mock_parse, mock_index):
    mock_index.return_value = {"documents": 1, "chunks": 2}

    result = rebuild_legal_parser_index(parse_docx=False)

    mock_parse.assert_not_called()
    mock_index.assert_called_once_with()
    assert result["parsed_documents"] == 0
    assert result["index"]["documents"] == 1
