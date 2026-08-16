from extractors.basic_metadata import MetadataExtractor
from models.document import CleanedDocument


def test_metadata_extractor_extracts_core_fields():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[
            "وزارة الصحة / مكتب الوزير",
            "الموضوع / تأليف لجنة لدراسة المطالب",
            "ربطًا قرار مجلس الوزراء رقم ( 245 ) لسنة 2024، المأخوذ في الجلسة الاعتيادية الثالثة المنعقدة في 30/12/2024 .",
            "المُرافقات :",
            "الأوليات ذات العلاقة .",
            "د. مثال",
            "الأمين العام لمجلس الوزراء",
            "31/12/2024",
        ],
        tables=[],
        raw_text="\n".join(
            [
                "وزارة الصحة / مكتب الوزير",
                "الموضوع / تأليف لجنة لدراسة المطالب",
                "ربطًا قرار مجلس الوزراء رقم ( 245 ) لسنة 2024، المأخوذ في الجلسة الاعتيادية الثالثة المنعقدة في 30/12/2024 .",
                "المُرافقات :",
                "الأوليات ذات العلاقة .",
                "د. مثال",
                "الأمين العام لمجلس الوزراء",
                "31/12/2024",
            ]
        ),
    )

    metadata = MetadataExtractor().extract(document)

    assert metadata.ministry == "وزارة الصحة"
    assert metadata.department == "مكتب الوزير"
    assert metadata.subject == "تأليف لجنة لدراسة المطالب"
    assert metadata.document_number == "245"
    assert metadata.document_year == "2024"
    assert metadata.session_date == "30/12/2024"
    assert metadata.issue_date == "31/12/2024"
    assert metadata.attachments == ["الأوليات ذات العلاقة"]
