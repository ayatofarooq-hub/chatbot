from app.extractors.semantic_extraction import parse_semantic_extraction_response


def test_parse_semantic_extraction_response_returns_structured_json() -> None:
    content = '{"executive_summary":"A decision was made.","legal_objective":"Implement the policy.","decision_outcome":"Approved.","obligations":["Report weekly"],"responsible_entities":["Ministry"],"implementation_requirements":["Submit form"],"legal_references":["Article 5"],"affected_organizations":["Council"],"legal_keywords":["decision"]}'

    payload = parse_semantic_extraction_response(content)

    assert payload["executive_summary"] == "A decision was made."
    assert payload["obligations"] == ["Report weekly"]
    assert payload["legal_keywords"] == ["decision"]
