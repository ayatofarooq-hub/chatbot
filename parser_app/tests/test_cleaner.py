from cleaners.text_cleaner import DocumentCleaner
from models.document import Document


def test_cleaner_removes_page_artifacts_and_preserves_legal_content():
    document = Document(
        filename="document1.txt",
        extension=".txt",
        pages=[],
        paragraphs=[
            "وزارة الصحة",
            "المادة ( 2 ) من تعليمات تنفيذ العقود الحكومية",
            "(1-2)",
            "هاني 9/6/2021 (2-2) هاني 9/6/2021 (2-2)",
            "أولا : الموافقة على الطلب بمبلغ 100 دولار",
        ],
        tables=[],
        raw_text="",
    )

    cleaned = DocumentCleaner().clean(document)

    assert "(1-2)" not in cleaned.paragraphs
    assert all("هاني 9/6/2021" not in paragraph for paragraph in cleaned.paragraphs)
    assert "المادة ( 2 ) من تعليمات تنفيذ العقود الحكومية" in cleaned.paragraphs
    assert "أولا : الموافقة على الطلب بمبلغ 100 دولار" in cleaned.paragraphs
