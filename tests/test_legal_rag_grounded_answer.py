from legal_rag.grounded_answer import (
    INSUFFICIENT_CONTEXT,
    MISSING_DECISION_NUMBER_ANSWER,
    NO_USABLE_LEGAL_SOURCE_TEXT,
    answer_from_results,
    build_document_answer_context,
    build_source_context,
    extracted_sources,
    full_texts_for_sources,
    product_price_answer_from_sources,
    wants_full_document_context,
    _full_text_from_payload,
)
from app.retrieval_logging import LOGGER_NAME


RESULTS = {
    "documents": [[
        (
            "أولًا :\n"
            "الموافقة على العقد المبرم بين شركة نفط البصرة وشركة المشاريع النفطية "
            "بمبلغ (4.594.000.050) دولار."
        )
    ]],
    "metadatas": [[
        {
            "chunk_id": "legal_json_test_item_1",
            "source_file": "قرار توصية الطاقة حقل الناصرية.docx",
            "section": "أولًا",
            "item_number": "أولًا",
            "paragraph_indexes": "3,4",
            "page_number": 1,
        }
    ]],
    "distances": [[0.1]],
    "relevance_scores": [[0.88]],
}

MULTI_RESULTS = {
    "documents": [[
        RESULTS["documents"][0][0],
        "ثانيًا : تتحمل شركة نفط البصرة وشركة المشاريع النفطية صحة الإجراءات القانونية.",
    ]],
    "metadatas": [[
        RESULTS["metadatas"][0][0],
        {
            "chunk_id": "legal_json_test_item_2",
            "source_file": "قرار توصية الطاقة حقل الناصرية.docx",
            "section": "ثانيًا",
            "item_number": "ثانيًا",
            "page_number": 1,
        },
    ]],
    "distances": [[0.1, 0.2]],
    "relevance_scores": [[0.88, 0.5]],
}


FUEL_PRICE_LONG_TEXT = (
    "قــرار\n"
    "مجلــس الــوزراء\n"
    "رقــم (                     ) لسنــة 2024\n"
    "قــرّر مجلــس الــوزراء في جلستــه الاعتياديــة الرابعة والاربعين المنعقدة في 29/10/2024 \n"
    "إقرار توصية المجلس الوزاري للاقتصاد (24315 ق) ؛ بحسب الآتي:\n"
    "الموافقة على تعديل أسعار المنتجات النفطية المجهزة إلى شركة ناقلات النفط العراقية \n"
    "الواردة بكتاب وزارة النفط المرقم بالعدد ( و/623 ) المؤرخ في 15/8/2024 لتصبح كالآتي :\n"
    "منتوج زيت الوقود (150.000) دينار / م3 بدلًا من (350.000) دينار / م3 .\n"
    "منتوج زيت الغاز (400) دينار / لتر بدلًا من (750) دينار / لتر .\n"
    "د. حميــد نعيــم الغــزي\n"
    "الأميـن العـام لمجلـس الـوزراء\n"
    "30/10/2024"
)

FUEL_PRICE_RESULTS = {
    "documents": [[FUEL_PRICE_LONG_TEXT]],
    "metadatas": [[
        {
            "chunk_id": "fuel-price-full",
            "source_file": "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx",
            "document_id": "legal_json_60df7b9e0c09",
            "document_type": "قرار مجلس الوزراء",
            "year": "2024",
            "issue_date": "30/10/2024",
            "session_date": "29/10/2024",
            "reference_numbers": "و/623 | 15/8/2024",
            "recommendation_numbers": "24315 ق",
            "decision_number": "",
        }
    ]],
    "distances": [[0.1]],
    "relevance_scores": [[0.94]],
}


def answer_body(answer: str) -> str:
    return answer.split("\n\nمواضيع مقترحة من نفس النص:", 1)[0]


def assert_interactive_related_topics(answer: str):
    assert "مواضيع مقترحة من نفس النص:" in answer
    assert "هل تريد" in answer or "أستطيع مساعدتك" in answer


def test_required_fuel_price_decision_question_cases(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"fuel-price-full": {"chunk_id": "fuel-price-full"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx": FUEL_PRICE_LONG_TEXT,
        },
    )

    cases = [
        ("كم أصبح سعر زيت الوقود؟", "150.000 دينار / م3"),
        ("كم كان سعر زيت الوقود سابقًا؟", "350.000 دينار / م3"),
        ("كم أصبح سعر زيت الغاز؟", "400 دينار / لتر"),
        ("كم كان سعر زيت الغاز سابقًا؟", "750 دينار / لتر"),
        ("ما تاريخ إصدار القرار؟", "30/10/2024"),
        ("متى عقدت الجلسة؟", "29/10/2024"),
        ("ما رقم كتاب وزارة النفط؟", "و/623"),
        ("ما تاريخ كتاب وزارة النفط؟", "15/8/2024"),
        ("ما رقم توصية المجلس الوزاري للاقتصاد؟", "24315 ق"),
        ("ما رقم قرار مجلس الوزراء؟", MISSING_DECISION_NUMBER_ANSWER),
    ]

    for question, expected in cases:
        result = answer_from_results(question, FUEL_PRICE_RESULTS, qwen_caller=lambda *_args: "wrong")
        assert expected in result["answer"]

    full_text_result = answer_from_results(
        "أعطني نص القرار كاملًا.",
        FUEL_PRICE_RESULTS,
        qwen_caller=lambda *_args: "خلاصة القرار: تعديل أسعار منتوجي زيت الوقود وزيت الغاز.",
    )
    assert answer_body(full_text_result["answer"]) == "خلاصة القرار: تعديل أسعار منتوجي زيت الوقود وزيت الغاز."
    assert_interactive_related_topics(full_text_result["answer"])
    assert full_text_result["full_text_sources"][0]["original_long_text"] == FUEL_PRICE_LONG_TEXT

    def answer_from_long_text(_question, context):
        assert FUEL_PRICE_LONG_TEXT in context
        return "مضمون القرار هو تعديل أسعار منتوجي زيت الوقود وزيت الغاز استنادًا إلى كتاب وزارة النفط."

    summary_result = answer_from_results(
        "ما مضمون القرار؟",
        FUEL_PRICE_RESULTS,
        qwen_caller=answer_from_long_text,
    )
    assert "تعديل أسعار منتوجي زيت الوقود وزيت الغاز" in summary_result["answer"]


def test_retrieval_logging_includes_required_diagnostics(monkeypatch, caplog):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"fuel-price-full": {"chunk_id": "fuel-price-full"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx": FUEL_PRICE_LONG_TEXT,
        },
    )

    with caplog.at_level("INFO", logger=LOGGER_NAME):
        answer_from_results("كم أصبح سعر زيت الغاز؟", FUEL_PRICE_RESULTS, qwen_caller=lambda *_args: "wrong")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "[RETRIEVAL]" in log_text
    assert "Question: كم أصبح سعر زيت الغاز؟" in log_text
    assert "[RETRIEVED DOCUMENTS]" in log_text
    assert "قرار توصية الاقتصاد تعديل سعر منتوجي زيت الوقود وزيت الغاز.docx" in log_text
    assert "[DOCUMENT SCORES]" in log_text
    assert "0.94" in log_text
    assert "[SELECTED DOCUMENT]" in log_text
    assert "[JSON FILE]" in log_text
    assert "[LONG_TEXT]" in log_text
    assert "Found: true" in log_text
    assert "[CONTEXT]" in log_text
    assert "[ANSWER GENERATION]" in log_text


def test_context_uses_required_source_block_format():
    sources = extracted_sources(RESULTS)
    context = build_source_context(sources)

    assert "SOURCE 1" in context
    assert "Document: قرار توصية الطاقة حقل الناصرية.docx" in context
    assert "Section: أولًا" in context
    assert "Item: أولًا" in context
    assert "Text:\nأولًا" in context
    assert "4.594.000.050" in context
    assert "PRIMARY LONG TEXT" not in context


def test_document_answer_context_uses_structured_full_source_text(monkeypatch):
    sources = extracted_sources(RESULTS)
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "Ù‚Ø±Ø§Ø± ØªÙˆØµÙŠØ© Ø§Ù„Ø·Ø§Ù‚Ø© Ø­Ù‚Ù„ Ø§Ù„Ù†Ø§ØµØ±ÙŠØ©.docx": "FULL LONG TEXT FOR WHOLE DECISION",
        },
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {sources[0].document: "FULL LONG TEXT FOR WHOLE DECISION"},
    )
    results = {
        **RESULTS,
        "metadatas": [[
            {
                **RESULTS["metadatas"][0][0],
                "title": "قــرار مجلــس الــوزراء",
                "document_type": "قرار مجلس الوزراء",
                "year": "2024",
                "issue_date": "30/10/2024",
                "session_number": "الرابعة والاربعين",
                "session_date": "29/10/2024",
                "document_reference_numbers": "و/623 | 15/8/2024",
                "recommendation_numbers": "24315 ق",
                "entities": "وزارة النفط | شركة ناقلات النفط العراقية",
            }
        ]],
    }

    context = build_document_answer_context(results, sources)

    assert "DOCUMENT 1" in context
    assert "Title:\nقــرار مجلــس الــوزراء" in context
    assert "Type:\nقرار مجلس الوزراء" in context
    assert "Year:\n2024" in context
    assert "Issue Date:\n30/10/2024" in context
    assert "Session:\nالرابعة والاربعين" in context
    assert "Session Date:\n29/10/2024" in context
    assert "References:\nو/623\n15/8/2024\n24315 ق" in context
    assert "Entities:\nوزارة النفط\nشركة ناقلات النفط العراقية" in context
    assert "FULL SOURCE TEXT:\nFULL LONG TEXT FOR WHOLE DECISION" in context


def test_full_text_sources_do_not_use_chunk_as_source_of_truth(monkeypatch):
    monkeypatch.setattr("legal_rag.grounded_answer.load_full_text_index", lambda: {})

    records = full_texts_for_sources(extracted_sources(RESULTS))

    assert records == []


def test_json_source_without_usable_text_returns_clear_error_without_llm(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"empty-json": {"chunk_id": "empty-json"}}},
    )
    monkeypatch.setattr("legal_rag.grounded_answer.load_full_text_index", lambda: {})
    results = {
        "documents": [["SHORT CHUNK THAT MUST NOT BE USED AS SOURCE OF TRUTH"]],
        "metadatas": [[
            {
                "chunk_id": "empty-json",
                "source_file": "empty.json",
                "source_type": "legal_document_parser_json",
                "json_path": "legal_document_parser/output/json/empty.json",
                "has_full_document": True,
            }
        ]],
        "distances": [[0.1]],
        "relevance_scores": [[0.5]],
    }

    def fail_if_called(*_args):
        raise AssertionError("LLM should not be called without usable source text")

    result = answer_from_results("ما مضمون القرار؟", results, qwen_caller=fail_if_called)

    assert result["answer"] == NO_USABLE_LEGAL_SOURCE_TEXT
    assert result["full_text"] == ""
    assert result["full_text_sources"] == []
    assert result["confidence"] == 0.0


def test_full_document_question_detection():
    assert wants_full_document_context("أعطني نص القرار كاملًا")
    assert wants_full_document_context("ما هو مضمون هذا القرار؟")
    assert wants_full_document_context("ما الذي قرره مجلس الوزراء في هذا القرار؟")
    assert not wants_full_document_context("كم أصبح سعر زيت الغاز؟")


def test_product_price_answer_extracts_diesel_from_long_text_source():
    sources = extracted_sources(
        {
            "documents": [["منتوج زيت الغاز (400) دينار / لتر بدلًا من (750) دينار / لتر ."]],
            "metadatas": [[{"chunk_id": "fuel", "source_file": "decision.docx"}]],
        }
    )

    assert product_price_answer_from_sources(
        "ما الذي قرره مجلس الوزراء بشأن زيت الغاز؟",
        sources,
    ) == "تم تعديل سعر منتوج زيت الغاز ليصبح 400 دينار / لتر بدلًا من 750 دينار / لتر."


def test_answer_from_results_uses_long_text_for_diesel_decision(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"fuel": {"chunk_id": "fuel"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "fuel-decision.docx": (
                "قــرار مجلس الوزراء\n"
                "منتوج زيت الوقود (150.000) دينار / م3 بدلًا من (350.000) دينار / م3 .\n"
                "منتوج زيت الغاز (400) دينار / لتر بدلًا من (750) دينار / لتر ."
            )
        },
    )
    results = {
        "documents": [["منتوج زيت الغاز"]],
        "metadatas": [[
            {
                "chunk_id": "fuel",
                "source_file": "fuel-decision.docx",
                "document_type": "قرار مجلس الوزراء",
                "year": "2024",
                "issue_date": "30/10/2024",
            }
        ]],
        "distances": [[0.1]],
        "relevance_scores": [[0.94]],
    }

    result = answer_from_results(
        "ما الذي قرره مجلس الوزراء بشأن زيت الغاز؟",
        results,
        qwen_caller=lambda *_args: "wrong",
    )

    assert answer_body(result["answer"]) == "تم تعديل سعر منتوج زيت الغاز ليصبح 400 دينار / لتر بدلًا من 750 دينار / لتر."
    assert_interactive_related_topics(result["answer"])
    assert result["full_text_sources"][0]["original_long_text"].startswith("قــرار مجلس الوزراء")


def test_answer_from_results_distinguishes_issue_and_session_dates(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"date-chunk": {"chunk_id": "date-chunk"}}},
    )
    results = {
        "documents": [["قرار مجلس الوزراء"]],
        "metadatas": [[
            {
                "chunk_id": "date-chunk",
                "source_file": "decision.docx",
                "issue_date": "30/10/2024",
                "session_date": "29/10/2024",
            }
        ]],
        "distances": [[0.1]],
        "relevance_scores": [[0.9]],
    }

    issue_result = answer_from_results("متى صدر القرار؟", results, qwen_caller=lambda *_args: "wrong")
    session_result = answer_from_results("متى عقدت الجلسة؟", results, qwen_caller=lambda *_args: "wrong")

    assert answer_body(issue_result["answer"]) == "تاريخ صدور القرار: 30/10/2024."
    assert answer_body(session_result["answer"]) == "تاريخ انعقاد الجلسة: 29/10/2024."


def test_answer_from_results_extracts_source_book_from_long_text(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"fuel": {"chunk_id": "fuel"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "fuel-decision.docx": (
                "الموافقة على تعديل أسعار المنتجات النفطية المجهزة إلى شركة ناقلات النفط العراقية\n"
                "الواردة بكتاب وزارة النفط المرقم بالعدد ( و/623 ) المؤرخ في 15/8/2024 لتصبح كالآتي :"
            )
        },
    )
    results = {
        "documents": [["تعديل أسعار المنتجات النفطية"]],
        "metadatas": [[{"chunk_id": "fuel", "source_file": "fuel-decision.docx"}]],
        "distances": [[0.1]],
        "relevance_scores": [[0.9]],
    }

    result = answer_from_results(
        "بناءً على أي كتاب تم تعديل الأسعار؟",
        results,
        qwen_caller=lambda *_args: "wrong",
    )

    assert answer_body(result["answer"]) == "كتاب وزارة النفط المرقم بالعدد (و/623) المؤرخ في 15/8/2024."
    assert_interactive_related_topics(result["answer"])
    assert result["full_text_sources"][0]["original_long_text"].startswith("الموافقة على تعديل أسعار")


def test_answer_wrapper_cites_only_retrieved_sources(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )

    result = answer_from_results(
        "ما هو مبلغ العقد؟",
        RESULTS,
        qwen_caller=lambda _question, context: (
            "مبلغ العقد هو (4.594.000.050) دولار."
            if "4.594.000.050" in context
            else "wrong"
        ),
    )

    assert result["answer"].startswith("مبلغ العقد هو (4.594.000.050) دولار.")
    assert "النص القانوني الكامل:" not in result["answer"]
    assert "الموافقة على العقد المبرم" not in result["answer"]
    assert result["confidence"] == 0.88
    source = result["full_text_sources"][0]
    assert source["paragraph_indexes"] == [3, 4]
    assert source["original_long_text"] == source["full_text"]
    assert "4.594.000.050" in source["relevant_text"]
    assert source["filename"].endswith(".docx")


def test_full_document_question_uses_original_long_text_in_model_context(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "قرار توصية الطاقة حقل الناصرية.docx": "FULL LONG TEXT FOR WHOLE DECISION",
            "قرار توصية الطاقة حقل الناصرية": "FULL LONG TEXT FOR WHOLE DECISION",
        },
    )

    result = answer_from_results(
        "أعطني نص القرار كاملًا",
        RESULTS,
        qwen_caller=lambda _question, context: (
            "تم استخدام النص الكامل"
            if "FULL LONG TEXT FOR WHOLE DECISION" in context
            else "wrong"
        ),
    )

    assert answer_body(result["answer"]) == "تم استخدام النص الكامل"
    assert result["full_text_sources"][0]["original_long_text"] == "FULL LONG TEXT FOR WHOLE DECISION"


def test_specific_question_keeps_model_context_on_relevant_text(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {
            "قرار توصية الطاقة حقل الناصرية.docx": "FULL LONG TEXT FOR WHOLE DECISION",
            "قرار توصية الطاقة حقل الناصرية": "FULL LONG TEXT FOR WHOLE DECISION",
        },
    )

    result = answer_from_results(
        "كم أصبح سعر زيت الغاز؟",
        RESULTS,
        qwen_caller=lambda _question, context: (
            "مبلغ العقد هو (4.594.000.050) دولار."
            if "FULL SOURCE TEXT:" in context
            and "FULL LONG TEXT FOR WHOLE DECISION" in context
            and "4.594.000.050" in context
            else "wrong"
        ),
    )

    assert result["answer"].startswith("مبلغ العقد هو")
    assert result["full_text_sources"][0]["original_long_text"] == "FULL LONG TEXT FOR WHOLE DECISION"


def test_missing_decision_number_is_not_inferred_from_reference_number(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )
    results = {
        **RESULTS,
        "metadatas": [[
            {
                **RESULTS["metadatas"][0][0],
                "document_number": "",
                "decision_number": "",
                "law_number": "",
                "reference_numbers": "24315 ق",
            }
        ]],
    }

    result = answer_from_results(
        "ما رقم القرار؟",
        results,
        qwen_caller=lambda *_args: "wrong",
    )

    assert answer_body(result["answer"]) == MISSING_DECISION_NUMBER_ANSWER
    assert "24315" not in result["answer"]


def test_known_decision_number_is_answered_from_metadata(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )
    results = {
        **RESULTS,
        "metadatas": [[
            {
                **RESULTS["metadatas"][0][0],
                "decision_number": "15",
                "reference_numbers": "24315 ق",
            }
        ]],
    }

    result = answer_from_results("ما رقم القرار؟", results, qwen_caller=lambda *_args: "wrong")

    assert answer_body(result["answer"]) == "رقم القرار هو 15."
    assert result["sources"] == [
        {
            "document": "قرار توصية الطاقة حقل الناصرية.docx",
            "section": "أولًا",
            "item": "أولًا",
            "chunk_id": "legal_json_test_item_1",
        }
    ]


def test_answer_wrapper_omits_retrieved_but_unsupported_sources(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {
            "by_chunk_id": {
                "legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"},
                "legal_json_test_item_2": {"chunk_id": "legal_json_test_item_2"},
            }
        },
    )

    result = answer_from_results(
        "ما هو مبلغ العقد؟",
        MULTI_RESULTS,
        qwen_caller=lambda _question, _context: "مبلغ العقد هو (4.594.000.050) دولار.",
    )

    assert result["sources"] == [
        {
            "document": "قرار توصية الطاقة حقل الناصرية.docx",
            "section": "أولًا",
            "item": "أولًا",
            "chunk_id": "legal_json_test_item_1",
        }
    ]


def test_answer_wrapper_returns_full_text_when_model_is_conservative(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {"legal_json_test_item_1": {"chunk_id": "legal_json_test_item_1"}}},
    )

    result = answer_from_results(
        "ماهي الموافقة؟",
        RESULTS,
        qwen_caller=lambda *_args: INSUFFICIENT_CONTEXT,
    )

    assert "الموافقة على العقد المبرم" in result["answer"]
    assert "النص القانوني الكامل:" not in result["answer"]
    assert result["sources"] == [
        {
            "document": "قرار توصية الطاقة حقل الناصرية.docx",
            "section": "أولًا",
            "item": "أولًا",
            "chunk_id": "legal_json_test_item_1",
        }
    ]


def test_unregistered_context_is_still_answered_from_word_text(monkeypatch):
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_registry",
        lambda: {"by_chunk_id": {}},
    )

    result = answer_from_results(
        "ما هو مبلغ العقد؟",
        RESULTS,
        qwen_caller=lambda *_args: "المبلغ هو (4.594.000.050) دولار.",
    )

    assert "4.594.000.050" in result["answer"]
    assert result["sources"][0]["chunk_id"] == "legal_json_test_item_1"


def test_empty_context_uses_full_text_fallback(monkeypatch):
    monkeypatch.setattr("legal_rag.grounded_answer.load_registry", lambda: {"by_chunk_id": {}})
    monkeypatch.setattr(
        "legal_rag.grounded_answer.load_full_text_index",
        lambda: {"fuel.docx": FUEL_PRICE_LONG_TEXT},
    )

    result = answer_from_results(
        "كم أصبح سعر زيت الغاز؟",
        {"documents": [[]], "metadatas": [[]], "distances": [[]]},
        qwen_caller=lambda *_args: "unused",
    )

    assert "400 دينار / لتر" in result["answer"]
    assert result["sources"][0]["document"] == "fuel.docx"


def test_full_text_payload_uses_long_text_before_body_or_paragraphs():
    payload = {
        "schema_version": "iraqi_legal_document.v2",
        "long_text": "PRIMARY LONG TEXT",
        "body": "BODY FALLBACK",
        "paragraphs": [{"text": "PARAGRAPH TEXT"}],
        "metadata": {"text": "METADATA TEXT"},
    }

    assert _full_text_from_payload(payload) == "PRIMARY LONG TEXT"


def test_full_text_payload_uses_body_fallback_without_paragraphs():
    payload = {
        "schema_version": "iraqi_legal_document.v2",
        "long_text": "",
        "body": "BODY FALLBACK",
        "paragraphs": [{"text": "PARAGRAPH TEXT"}],
    }

    assert _full_text_from_payload(payload) == "BODY FALLBACK"


def test_full_text_payload_reconstructs_paragraphs_only_without_long_text_or_body():
    payload = {
        "schema_version": "iraqi_legal_document.v2",
        "long_text": "",
        "body": "",
        "paragraphs": [{"text": "FIRST"}, {"text": "SECOND"}],
    }

    assert _full_text_from_payload(payload) == "FIRST\nSECOND"
