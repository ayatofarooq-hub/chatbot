from app.classifiers.metadata_extractor import extract_metadata


def test_extract_metadata_detects_common_fields() -> None:
    text = """
    Cabinet Decision No. 123/2024
    Issue Date: 2024-08-01
    Ministry: Ministry of Finance
    Subject: Budget Allocation
    From: Director General
    To: Department of Planning
    Signature: Minister
    Attachments: Annex 1
    Distribution List: Finance, Planning
    Reference Documents: Circular 10
    """

    metadata = extract_metadata(text)

    assert metadata["decision_number"] == "123/2024"
    assert metadata["issue_date"] == "2024-08-01"
    assert metadata["ministry"] == "Ministry of Finance"
    assert metadata["subject"] == "Budget Allocation"
    assert metadata["signature"] == "Minister"
