from extractors.legal_extraction_engine import LegalExtractionEngine
from models.document import CleanedDocument, LlmLegalAnalysis
from tests.conftest import sample_document_type, sample_metadata


def test_legal_engine_uses_rules_and_metadata_before_llm():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[
            "قرار مجلس الوزراء رقم 245 لسنة 2024",
            "أولا: الموافقة على الطلب.",
            "تتحمل وزارة الصحة سلامة الإجراءات.",
        ],
        tables=[],
        raw_text="قرار مجلس الوزراء رقم 245 لسنة 2024\nأولا: الموافقة على الطلب.\nتتحمل وزارة الصحة سلامة الإجراءات.",
    )

    content = LegalExtractionEngine().extract(document, sample_metadata(), sample_document_type())

    assert content.legal_objective == "تأليف لجنة لدراسة المطالب"
    assert content.extraction_sources["legal_objective"] == "metadata"
    assert content.decision_outcome == "أولا: الموافقة على الطلب."
    assert content.implementation_responsibilities == ["تتحمل وزارة الصحة سلامة الإجراءات."]
    assert content.items == [
        {
            "id": 1,
            "type": "Legal Reference",
            "text": "قرار مجلس الوزراء رقم 245 لسنة 2024",
            "summary": None,
        },
        {
            "id": 2,
            "type": "Approval",
            "text": "أولا: الموافقة على الطلب.",
            "summary": None,
        },
        {
            "id": 3,
            "type": "Implementation",
            "text": "تتحمل وزارة الصحة سلامة الإجراءات.",
            "summary": None,
        },
    ]


def test_legal_engine_fills_only_missing_fields_from_llm():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=["قرار مجلس الوزراء", "تتحمل وزارة الصحة سلامة الإجراءات."],
        tables=[],
        raw_text="قرار مجلس الوزراء\nتتحمل وزارة الصحة سلامة الإجراءات.",
    )
    metadata = sample_metadata(subject=None)
    analysis = LlmLegalAnalysis(
        legal_meaning="LLM objective",
        structured_fields={"decision_outcome": "LLM outcome"},
        summary="LLM summary",
        model="qwen2.5:1.5b",
    )

    content = LegalExtractionEngine().extract(
        document,
        metadata,
        sample_document_type(),
        llm_analysis=analysis,
    )

    assert content.legal_objective == "LLM objective"
    assert content.executive_summary == "LLM summary"
    assert content.extraction_sources["legal_objective"] == "llm"


def test_legal_engine_uses_original_body_without_cleaning():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=["قرار مجلس الوزراء", "أولا: الموافقة على الطلب."],
        tables=[],
        raw_text="قرار مجلس الوزراء\nأولا: الموافقة على الطلب.",
    )
    original_body = "قرار مجلس الوزراء  \n\nأولا:  الموافقة على الطلب.\n"

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(),
        sample_document_type(),
        original_body=original_body,
    )

    assert content.body == original_body


def test_legal_engine_uses_original_paragraph_array():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=["قرار مجلس الوزراء", "أولا: الموافقة على الطلب."],
        tables=[],
        raw_text="قرار مجلس الوزراء\nأولا: الموافقة على الطلب.",
    )
    original_paragraphs = ["قرار مجلس الوزراء  ", "أولا:  الموافقة على الطلب."]

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(),
        sample_document_type(),
        original_paragraphs=original_paragraphs,
    )

    assert content.paragraphs == original_paragraphs
    assert content.items[0]["text"] == original_paragraphs[0]


def test_legal_engine_extracts_numbered_section_items():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[
            "قرار مجلس الوزراء",
            "أولا :",
            "الموافقة على العقد المبرم بين وزارة النفط وشركة نفط البصرة بمبلغ (1.250.000.000) دولار في 15/6/2024.",
            "المادة (1) من تعليمات تنفيذ العقود الحكومية (2 لسنة 2014).",
            "ثانيا : استثناء العقد المذكور آنفا.",
        ],
        tables=[],
        raw_text="",
    )

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(),
        sample_document_type(),
    )

    assert content.section_items[0]["id"] == 1
    assert content.section_items[0]["text"] == "قرار مجلس الوزراء"
    assert content.section_items[1]["text"] == (
        "أولا :\n"
        "الموافقة على العقد المبرم بين وزارة النفط وشركة نفط البصرة بمبلغ (1.250.000.000) دولار في 15/6/2024."
    )
    assert "وزارة النفط وشركة نفط البصرة بمبلغ (1" in content.section_items[1]["entities"]
    assert content.section_items[1]["money"] == ["(1.250.000.000) دولار"]
    assert content.section_items[1]["dates"] == ["15/6/2024"]
    assert content.section_items[2]["text"] == "المادة (1) من تعليمات تنفيذ العقود الحكومية (2 لسنة 2014)."
    assert content.section_items[2]["references"] == [
        "تعليمات تنفيذ العقود الحكومية (2 لسنة 2014)"
    ]
    assert content.section_items[3]["text"] == "ثانيا : استثناء العقد المذكور آنفا."


def test_legal_engine_extracts_categorized_legal_entities():
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[
            "وزارة النفط / مكتب الوزير",
            "توصية اللجنة المركزية في هيئة النزاهة بشأن مشروع توسعة حقل الناصرية.",
            "الموافقة على العقد بين شركة نفط البصرة ومجلس الوزراء.",
            "د. حميد نعيم الغزي",
        ],
        tables=[],
        raw_text=(
            "وزارة النفط / مكتب الوزير\n"
            "توصية اللجنة المركزية في هيئة النزاهة بشأن مشروع توسعة حقل الناصرية.\n"
            "الموافقة على العقد بين شركة نفط البصرة ومجلس الوزراء.\n"
            "د. حميد نعيم الغزي"
        ),
    )

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(
            ministry="وزارة النفط",
            department="مكتب الوزير",
            sender="وزارة النفط / مكتب الوزير",
            signature="د. حميد نعيم الغزي - الأمين العام",
        ),
        sample_document_type(),
    )

    assert "وزارة النفط" in content.legal_entities["ministries"]
    assert "شركة نفط البصرة" in content.legal_entities["companies"]
    assert "اللجنة المركزية" in content.legal_entities["committees"]
    assert "هيئة النزاهة" in content.legal_entities["authorities"]
    assert "مكتب الوزير" in content.legal_entities["government_offices"]
    assert "د. حميد نعيم الغزي" in content.legal_entities["people"]
    assert "مشروع توسعة حقل الناصرية" in content.legal_entities["projects"]
    assert "مجلس الوزراء" in content.legal_entities["councils"]


def test_legal_engine_extracts_structured_references():
    text = (
        "ربطاً قرار مجلس الوزراء رقم 245 لسنة 2024، "
        "وبموجب كتابها المرقم بالعدد ( و / 903 ) المؤرخ في 19/12/2024، "
        "واستناداً إلى قانون رقم 10 لسنة 2020، "
        "والمادة ( 2 / أولاً / د ) من تعليمات تنفيذ العقود الحكومية، "
        "وإقرار توصية المجلس الوزاري للطاقة ( 24090 ط ) لسنة 2024."
    )
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[text],
        tables=[],
        raw_text=text,
    )

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(),
        sample_document_type(),
    )

    assert content.references["decision_numbers"] == ["قرار مجلس الوزراء رقم 245 لسنة 2024"]
    assert content.references["book_numbers"] == ["كتابها المرقم بالعدد ( و / 903 )"]
    assert content.references["law_numbers"] == ["قانون رقم 10 لسنة 2020"]
    assert content.references["article_numbers"] == ["المادة ( 2 / أولاً / د )"]
    assert content.references["recommendation_numbers"] == [
        "توصية المجلس الوزاري للطاقة ( 24090 ط ) لسنة 2024"
    ]


def test_legal_engine_extracts_numeric_fields():
    text = (
        "الموافقة على العقد بمبلغ (1.250.000.000) دولار وهي أقل من الكلفة بمقدار (5.5%) "
        "لسنة 2024 ولفترة تجهيز (720) يوم لتجهيز أنبوب النفط الخام بطول (685) كم "
        "وبقطر (56) انج وبسمك (22) ملم وبعدد (15) طائرة وكمية (100) برميل."
    )
    document = CleanedDocument(
        filename="document1.docx",
        extension=".docx",
        pages=[],
        paragraphs=[text],
        tables=[],
        raw_text=text,
    )

    content = LegalExtractionEngine().extract(
        document,
        sample_metadata(),
        sample_document_type(),
    )

    assert content.extracted_fields["money"] == ["(1.250.000.000) دولار"]
    assert content.extracted_fields["percentages"] == ["(5.5%)"]
    assert content.extracted_fields["years"] == ["2024"]
    assert content.extracted_fields["durations"] == ["(720) يوم"]
    assert content.extracted_fields["pipe_lengths"] == ["بطول (685) كم"]
    assert content.extracted_fields["diameters"] == ["بقطر (56) انج"]
    assert content.extracted_fields["thickness"] == ["بسمك (22) ملم"]
    assert content.extracted_fields["quantities"] == ["بعدد (15) طائرة", "كمية (100) برميل"]
