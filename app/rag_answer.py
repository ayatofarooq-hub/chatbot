"""Answer Arabic legal questions using only retrieved local context."""

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import ollama
from chromadb.errors import NotFoundError

try:
    from .build_index import COLLECTION_NAME
    from .citation_registry import (
        chunk_id_for,
        filter_results_to_registered,
        load_registry,
        registry_warnings_for_metadatas,
    )
    from .config import (
        CHAT_MAX_TOKENS,
        CHAT_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
        retrieved_context_debug,
    )
    from .legal_lookup import answer_exact_law
    from .legal_source_text import NO_USABLE_LEGAL_SOURCE_TEXT, source_text_from_payload
    from .ollama_client import client as ollama_client
    from .prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
    )
    from .retrieval_logging import (
        log_answer_generation,
        log_long_text_status,
        log_retrieval_results,
    )
    from .search_index import search
    from .text_encoding import repair_mojibake
except ImportError:
    # Support direct execution with: python app/rag_answer.py
    from build_index import COLLECTION_NAME
    from citation_registry import (
        chunk_id_for,
        filter_results_to_registered,
        load_registry,
        registry_warnings_for_metadatas,
    )
    from config import (
        CHAT_MAX_TOKENS,
        CHAT_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
        retrieved_context_debug,
    )
    from legal_lookup import answer_exact_law
    from legal_source_text import NO_USABLE_LEGAL_SOURCE_TEXT, source_text_from_payload
    from ollama_client import client as ollama_client
    from prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
    )
    from retrieval_logging import (
        log_answer_generation,
        log_long_text_status,
        log_retrieval_results,
    )
    from search_index import search
    from text_encoding import repair_mojibake


CITATION_PATTERN = re.compile(
    r"\[المصدر:\s*(.+?)،\s*الصفحة:\s*([0-9٠-٩]+)\]"
)
NUMBER_PATTERN = re.compile(r"[0-9٠-٩]+")
LEGAL_TITLE_ONLY_PATTERN = re.compile(
    r"^\s*(?:[-•]\s*)?"
    r"(?:قانون|قرار|تعليمات|نظام)\s+.+?"
    r"(?:رقم\s*\(?[0-9٠-٩]+\)?\s+لسنة\s*\(?[0-9٠-٩]+\)?|"
    r"لسنة\s*\(?[0-9٠-٩]+\)?)\s*[.،؛:]*\s*$"
)
SECTION_SOURCE_PATTERN = re.compile(
    r"تفكيك القوانين من\s*\([^)]+\)\s*إلى\s*\([^)]+\)\s*-\s*[^\n\r]+"
)
LAW_ITEM_PATTERN = re.compile(
    r"(?<!\S)([0-9٠-٩]+)\.\s+(?:قانون|قرار|تعليمات|نظام)\s+"
)
SECTION_HEADING_PATTERN = re.compile(
    r"^\s*[1-4١-٤][.)-]?\s*"
    r"(خلاصة مختصرة|التفاصيل القانونية ذات الصلة|"
    r"ملاحظات لصانع القرار|المصادر|الجواب|المصدر)\s*:?\s*$"
)
PENALTY_STEMS = ("عقوب", "غرام", "سجن", "حبس", "إعدام")
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
GREETING_WORDS = {
    "اهلا",
    "أهلا",
    "السلام عليكم",
    "السلام عليكم ورحمة الله",
    "مرحبا",
    "مرحباً",
    "هلا",
    "hello",
    "hi",
}
THANKS_WORDS = {
    "شكرا",
    "شكراً",
    "شكرا لك",
    "شكراً لك",
    "مشكور",
    "thanks",
    "thank you",
}
MISSING_DECISION_NUMBER_ANSWER = "رقم القرار غير مثبت في النص المستخرج من الوثيقة."
RELATED_TOPICS_HEADING = "مواضيع مقترحة من نفس النص:"
SOURCE_JSON_DIRS = (
    "data/legal_documents",
    "data/extracted_text",
    "data/output",
    "legal_document_parser/output/json",
    "parser_app/data/output",
    "dataset",
)


@dataclass(frozen=True)
class AnswerResult:
    """Generated answer and any citation-vetting warnings."""

    content: str
    warnings: list[str]


def get_question() -> str:
    """Read an Arabic legal question from arguments or an interactive prompt."""

    parser = argparse.ArgumentParser(
        description="Answer an Arabic legal question from the local RAG index."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Arabic legal question to answer.",
    )
    arguments = parser.parse_args()

    question = " ".join(arguments.question).strip()
    if not question:
        question = input("أدخل السؤال القانوني: ").strip()

    if not question:
        raise ValueError("لا يمكن أن يكون السؤال فارغاً.")

    return question


def normalize_short_message(message: str) -> str:
    """Normalize a short conversational message for exact local matching."""

    message = message.strip().lower()
    message = re.sub(r"[!؟?،,.]+$", "", message)
    return re.sub(r"\s+", " ", message)


def get_quick_response(question: str) -> str | None:
    """Return a local response for simple messages that need no legal RAG."""

    normalized_question = normalize_short_message(question)

    if len(normalized_question) < 3:
        return "يرجى كتابة سؤال قانوني مكتمل حتى أتمكن من البحث والإجابة."

    if normalized_question in GREETING_WORDS:
        return "مرحباً، كيف يمكنني مساعدتك في سؤالك القانوني العراقي؟"

    if normalized_question in THANKS_WORDS:
        return "على الرحب والسعة."

    return None


def citation_for_metadata(metadata: dict, registry: dict) -> dict:
    """Return the registry-backed citation for retrieved metadata."""

    chunk_id = chunk_id_for(metadata)
    if not chunk_id:
        return {}
    return registry.get("by_chunk_id", {}).get(chunk_id, {})


def citation_source_label(metadata: dict, registry: dict) -> str:
    """Return a reader-facing legal source label instead of an internal id."""

    citation = citation_for_metadata(metadata, registry)
    return str(
        citation.get("legal_reference")
        or citation.get("law_name")
        or metadata.get("document_title")
        or metadata.get("source_file")
        or metadata.get("document_type")
        or ""
    ).strip()


def build_context(results: dict, registry: dict | None = None) -> str:
    """Format retrieved documents as the structured answer-generator context."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    relevance_scores = results.get("relevance_scores", [[]])[0]
    registry = registry or load_registry()
    context_sections = []

    def metadata_text(metadata: dict, citation: dict, *keys: str) -> str:
        for key in keys:
            value = _clean_source_value(metadata.get(key))
            if value:
                return repair_mojibake(value)
        for key in keys:
            value = _clean_source_value(citation.get(key))
            if value:
                return repair_mojibake(value)
        return ""

    def split_metadata_values(*values: object) -> list[str]:
        items = []
        for value in values:
            if isinstance(value, list):
                candidates = value
            else:
                candidates = re.split(r"\s*\|\s*|\n+", str(value or ""))
            for candidate in candidates:
                text = repair_mojibake(_clean_source_value(candidate))
                if text:
                    items.append(text)
        return list(dict.fromkeys(items))

    def context_list(label: str, values: list[str]) -> list[str]:
        return [f"{label}:", *(values or ["غير مثبت"])]

    for rank, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        citation = citation_for_metadata(metadata, registry)
        source_file = _clean_source_value(metadata.get("source_file"))
        relevance_score = relevance_scores[rank - 1] if rank <= len(relevance_scores) else ""
        resolved_full_source_text = _source_text_for_metadata(metadata)
        full_source_text = resolved_full_source_text or "غير مثبت في JSON الأصلي"
        references = split_metadata_values(
            metadata.get("document_reference_numbers"),
            metadata.get("reference_numbers"),
            metadata.get("recommendation_numbers"),
            metadata.get("legal_reference"),
            citation.get("legal_reference"),
        )
        entities = split_metadata_values(
            metadata.get("entities"),
            metadata.get("organizations"),
            metadata.get("companies"),
            metadata.get("persons"),
        )
        context_sections.append(
            "\n".join(
                [
                    f"DOCUMENT {rank}",
                    "",
                    "Source:",
                    repair_mojibake(source_file or citation_source_label(metadata, registry)),
                    "",
                    "Relevance Score:",
                    _clean_source_value(relevance_score) or "غير مثبت",
                    "",
                    "Title:",
                    metadata_text(metadata, citation, "title", "document_title", "law_name")
                    or repair_mojibake(citation_source_label(metadata, registry)),
                    "",
                    "Type:",
                    metadata_text(metadata, citation, "document_type", "classification", "document_classification")
                    or "غير مثبت",
                    "",
                    "Year:",
                    metadata_text(metadata, citation, "year", "law_year") or "غير مثبت",
                    "",
                    "Issue Date:",
                    metadata_text(metadata, citation, "issue_date") or "غير مثبت",
                    "",
                    "Session:",
                    metadata_text(metadata, citation, "session_number") or "غير مثبت",
                    "",
                    "Session Date:",
                    metadata_text(metadata, citation, "session_date") or "غير مثبت",
                    "",
                    *context_list("References", references),
                    "",
                    *context_list("Entities", entities),
                    "",
                    "RELEVANT RETRIEVED TEXT:",
                    repair_mojibake(document),
                    "",
                    "FULL SOURCE TEXT:",
                    full_source_text,
                ]
            )
        )

    context = "\n\n".join(context_sections)
    top_metadata = metadatas[0] if metadatas and isinstance(metadatas[0], dict) else {}
    top_source_text = _source_text_for_metadata(top_metadata) if top_metadata else ""
    context_status = (
        "Full document loaded"
        if top_source_text and results.get("documents", [[]])[0] and results["documents"][0][0] == top_source_text
        else "Structured context built"
    )
    log_long_text_status(top_metadata, bool(top_source_text), context_status, len(context))
    if len(context_sections) > 1:
        instruction = (
            "MULTI-DOCUMENT SOURCE RULE:\n"
            "Mention the supporting source for each distinct finding using DOCUMENT number, title, or source label."
        )
        return f"{instruction}\n\n{context}"
    return context


def asks_for_decision_number(question: str) -> bool:
    """Return whether the user asks specifically for the decision number."""

    text = repair_mojibake(str(question or "")).strip()
    return bool(
        re.search(r"(?:ما|ماهو|ما\s+هو|اذكر|اعطني|أعطني).{0,30}رقم\s+القرار", text)
        or re.search(r"رقم\s+قرار\s+مجلس\s+الوزراء", text)
    )


def _decision_number_from_results(results: dict) -> str:
    metadatas = results.get("metadatas", [[]])[0]
    metadata = metadatas[0] if metadatas and isinstance(metadatas[0], dict) else {}
    return _clean_source_value(metadata.get("decision_number"))


def decision_number_answer(question: str, results: dict) -> AnswerResult | None:
    """Answer decision-number questions without using recommendation/book numbers."""

    if not asks_for_decision_number(question):
        return None
    decision_number = _decision_number_from_results(results)
    if decision_number:
        return AnswerResult(content=f"رقم القرار هو {decision_number}.", warnings=[])
    return AnswerResult(content=MISSING_DECISION_NUMBER_ANSWER, warnings=[])


def _top_metadata(results: dict) -> dict:
    metadatas = results.get("metadatas", [[]])[0]
    return metadatas[0] if metadatas and isinstance(metadatas[0], dict) else {}


def _metadata_requires_original_source_text(metadata: dict) -> bool:
    if not metadata:
        return False
    if metadata.get("json_path") or metadata.get("original_json_path"):
        return True
    if str(metadata.get("source_type") or "") == "legal_document_parser_json":
        return True
    if str(metadata.get("full_source_resolver") or "") == "json":
        return True
    return False


def unusable_source_text_answer(results: dict) -> AnswerResult | None:
    """Return a hard error when a JSON-backed source has no usable original text."""

    metadata = _top_metadata(results)
    if not _metadata_requires_original_source_text(metadata):
        return None
    if _source_text_for_metadata(metadata):
        return None
    return AnswerResult(content=NO_USABLE_LEGAL_SOURCE_TEXT, warnings=[NO_USABLE_LEGAL_SOURCE_TEXT])


def requested_document_date_field(question: str) -> tuple[str, str] | None:
    """Return the exact metadata date field requested by the question."""

    text = repair_mojibake(str(question or "")).strip()
    if re.search(r"(?:متى|تاريخ).{0,30}(?:عقدت|انعقدت|انعقاد).{0,20}الجلسة", text):
        return "session_date", "تاريخ انعقاد الجلسة"
    if re.search(r"(?:متى|تاريخ).{0,30}(?:صدر|صدور|اصدار|إصدار).{0,20}(?:القرار|الوثيقة)", text):
        return "issue_date", "تاريخ صدور القرار"
    return None


def document_date_answer(question: str, results: dict) -> AnswerResult | None:
    """Answer date questions from explicit metadata without mixing date types."""

    requested = requested_document_date_field(question)
    if not requested:
        return None
    field, label = requested
    value = _clean_source_value(_top_metadata(results).get(field))
    if value:
        return AnswerResult(content=f"{label}: {value}.", warnings=[])
    return AnswerResult(content=f"{label} غير مثبت في النص المستخرج من الوثيقة.", warnings=[])


def asks_for_recommendation_number(question: str) -> bool:
    text = repair_mojibake(str(question or "")).strip()
    return bool(re.search(r"رقم.{0,30}توصية.{0,40}المجلس\s+الوزاري\s+للاقتصاد", text))


def _recommendation_number_from_text(text: str) -> str:
    match = re.search(r"توصية\s+المجلس\s+الوزاري\s+للاقتصاد\s*\(\s*([^)]+?)\s*\)", repair_mojibake(str(text or "")))
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def recommendation_number_answer(question: str, results: dict) -> AnswerResult | None:
    """Answer recommendation-number questions without treating it as a decision number."""

    if not asks_for_recommendation_number(question):
        return None
    metadata_value = _clean_source_value(_top_metadata(results).get("recommendation_numbers"))
    if metadata_value:
        return AnswerResult(content=f"رقم توصية المجلس الوزاري للاقتصاد: {metadata_value}.", warnings=[])
    for text in _texts_for_source_book_lookup(results):
        number = _recommendation_number_from_text(text)
        if number:
            return AnswerResult(content=f"رقم توصية المجلس الوزاري للاقتصاد: {number}.", warnings=[])
    return AnswerResult(content="رقم توصية المجلس الوزاري للاقتصاد غير مثبت في النص المستخرج من الوثيقة.", warnings=[])


def asks_for_source_book(question: str) -> bool:
    """Return whether the user asks which official book/document a decision relied on."""

    text = repair_mojibake(str(question or "")).strip()
    return bool(
        re.search(r"(?:بناء|استناد).{0,20}(?:على|إلى|الى).{0,40}(?:اي|أي)\s+كتاب", text)
        or re.search(r"(?:اي|أي)\s+كتاب.{0,60}(?:تعديل|عدلت|تعدلت)", text)
        or re.search(r"كتاب.{0,40}(?:تم|جرى).{0,40}تعديل", text)
        or re.search(r"(?:رقم|تاريخ).{0,20}كتاب", text)
    )


def _texts_for_source_book_lookup(results: dict) -> list[str]:
    texts = []
    metadatas = results.get("metadatas", [[]])[0]
    documents = results.get("documents", [[]])[0]
    for metadata in metadatas:
        if isinstance(metadata, dict):
            source_text = _source_text_for_metadata(metadata)
            if source_text:
                texts.append(source_text)
    texts.extend(str(document or "") for document in documents)
    return list(dict.fromkeys(texts))


def _reference_book_from_text(text: str) -> str:
    normalized_text = repair_mojibake(str(text or ""))
    pattern = re.compile(
        r"كتاب\s+(.{0,80}?)\s+المرقم\s+بالعدد\s*\(\s*([^)]+?)\s*\)\s+المؤرخ\s+في\s+([0-9٠-٩/\\-]+)",
        flags=re.DOTALL,
    )
    for match in pattern.finditer(normalized_text):
        issuer, number, date = [re.sub(r"\s+", " ", value).strip(" .،؛:") for value in match.groups()]
        if not number or not date:
            continue
        issuer_text = f"كتاب {issuer}" if issuer else "الكتاب"
        return f"{issuer_text} المرقم بالعدد ({number}) المؤرخ في {date}."
    return ""


def _reference_book_parts_from_text(text: str) -> tuple[str, str, str] | None:
    normalized_text = repair_mojibake(str(text or ""))
    pattern = re.compile(
        r"كتاب\s+(.{0,80}?)\s+المرقم\s+بالعدد\s*\(\s*([^)]+?)\s*\)\s+المؤرخ\s+في\s+([0-9٠-٩/\\-]+)",
        flags=re.DOTALL,
    )
    match = pattern.search(normalized_text)
    if not match:
        return None
    issuer, number, date = [re.sub(r"\s+", " ", value).strip(" .،؛:") for value in match.groups()]
    return issuer, number, date


def source_book_answer(question: str, results: dict) -> AnswerResult | None:
    """Answer source-book questions from long_text without inventing a source."""

    if not asks_for_source_book(question):
        return None
    question_text = repair_mojibake(str(question or ""))
    for text in _texts_for_source_book_lookup(results):
        parts = _reference_book_parts_from_text(text)
        if not parts:
            continue
        issuer, number, date = parts
        issuer_label = issuer or "الكتاب"
        if re.search(r"رقم.{0,20}كتاب", question_text):
            return AnswerResult(content=f"رقم كتاب {issuer_label}: {number}.", warnings=[])
        if re.search(r"تاريخ.{0,20}كتاب", question_text):
            return AnswerResult(content=f"تاريخ كتاب {issuer_label}: {date}.", warnings=[])
        issuer_text = f"كتاب {issuer_label}" if issuer else "الكتاب"
        return AnswerResult(content=f"{issuer_text} المرقم بالعدد ({number}) المؤرخ في {date}.", warnings=[])
    return AnswerResult(content="الكتاب الذي استند إليه تعديل الأسعار غير مثبت في النص المستخرج من الوثيقة.", warnings=[])


def wants_full_document_context(question: str) -> bool:
    """Return whether the user is asking for the complete retrieved document."""

    text = repair_mojibake(str(question or "")).strip()
    patterns = (
        r"\b(?:النص|نص)\s+(?:الكامل|كامل[اً]?)\b",
        r"\b(?:اعطني|أعطني|اريد|أريد)\s+(?:نص|النص).{0,30}(?:كامل|كاملا|كاملًا)\b",
        r"\b(?:مضمون|ملخص|خلاصة)\s+(?:هذا\s+)?(?:القرار|الوثيقة|المستند)\b",
        r"\bما\s+(?:هو\s+)?(?:مضمون|محتوى)\s+(?:هذا\s+)?(?:القرار|الوثيقة|المستند)\b",
        r"\bما\s+الذي\s+قرره\s+مجلس\s+الوزراء\b",
        r"\bماذا\s+قرر\s+مجلس\s+الوزراء\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def wants_exact_full_document_text(question: str) -> bool:
    text = repair_mojibake(str(question or "")).strip()
    return bool(
        re.search(r"\b(?:اعطني|أعطني|اريد|أريد)\s+(?:نص|النص).{0,30}(?:كامل|كاملا|كاملًا)\b", text)
        or re.search(r"\b(?:النص|نص)\s+(?:الكامل|كامل[اً]?)\b", text)
    )


def full_document_text_answer(question: str, results: dict) -> AnswerResult | None:
    """Do not return Word/docx long_text directly; the answer must be a summary."""

    return None


def results_with_full_document_context(results: dict) -> dict:
    """Use original long_text for the best retrieved document when needed."""

    metadatas = results.get("metadatas", [[]])[0]
    if not metadatas:
        return results
    top_metadata = metadatas[0] if isinstance(metadatas[0], dict) else {}
    source_text = _source_text_for_metadata(top_metadata)
    if not source_text:
        return results

    metadata = dict(top_metadata)
    metadata["retrieval_context"] = "full_document"
    return {
        **results,
        "documents": [[source_text]],
        "metadatas": [[metadata]],
        "distances": [[results.get("distances", [[0.0]])[0][0] if results.get("distances", [[]])[0] else 0.0]],
    }

def print_retrieved_context(context: str) -> None:
    """Print retrieved passages when diagnostic mode is enabled."""

    print()
    print("=== RETRIEVED CONTEXT DEBUG ===")
    print(context)
    print("=== END RETRIEVED CONTEXT ===")


def get_allowed_citations(
    results: dict,
    registry: dict | None = None,
) -> set[tuple[str, str]]:
    """Return valid source and page pairs from the retrieved results."""

    registry = registry or load_registry()
    metadatas = results.get("metadatas", [[]])[0]
    return {
        (
            repair_mojibake(citation_source_label(metadata, registry)),
            str(metadata.get("page_number")),
        )
        for metadata in metadatas
    }


def _clean_source_value(value: object) -> str:
    """Return a readable metadata value for source display."""

    text = repair_mojibake(str(value or "")).strip()
    return "" if text.lower() == "missing" else text


def _source_filename_label(value: object) -> str:
    """Return a readable filename/source label without internal upload prefixes."""

    text = _clean_source_value(value)
    if not text:
        return ""
    text = re.sub(r"^uploaded_[0-9a-f]{16}_", "", text)
    text = text.replace("_", " ")
    return text.strip()


def _is_generic_source_label(value: str) -> bool:
    """Return whether an extracted title is too vague to be useful as a source."""

    normalized = normalized_answer_text(value)
    generic_labels = {
        normalized_answer_text("قرار"),
        normalized_answer_text("قــرار"),
        normalized_answer_text("دائرة شؤون مجلس ال"),
        normalized_answer_text("دائرة شؤون مجلس الوزراء واللجان"),
    }
    return not normalized or normalized in generic_labels


def display_source_label(metadata: dict, citation: dict | None = None) -> str:
    """Return the best human-readable source label for a retrieved chunk."""

    citation = citation or {}
    source_file = _source_filename_label(
        metadata.get("document_original_filename")
        or citation.get("source_file")
        or metadata.get("source_file")
    )
    law_name = _clean_source_value(
        citation.get("law_name")
        or citation.get("legal_reference")
        or metadata.get("section_title")
        or metadata.get("document_title")
        or metadata.get("legal_reference")
    )

    if source_file and (
        str(metadata.get("source_file", "")).startswith("uploaded_")
        or str(metadata.get("document_upload_id", "")).strip()
        or _is_generic_source_label(law_name)
    ):
        return source_file
    return law_name or source_file


def uploaded_decision_source_label(document: object) -> str:
    """Infer a concise source title from an uploaded government decision."""

    text = repair_mojibake(str(document or ""))
    normalized = normalized_answer_text(text)
    if (
        "mi 17" in normalized
        or "mi17" in normalized
        or "الطائرات المروحية" in normalized
        or ("عقد تصليح" in normalized and "طائرات" in normalized)
    ):
        return "قرار استثناء عقد تصليح الطائرات المروحية"
    if "مصنع" in normalized and "زجاج" in normalized:
        return "قرار إقرار الضمانة السيادية مصنع الزجاج"

    subject_match = re.search(
        r"الموضوع\s*/\s*(?:[-ـ\s]*)(.+?)(?=\s+الحقًا|\s+لاحقًا|\n|$)",
        text,
        flags=re.DOTALL,
    )
    if subject_match:
        subject = re.sub(r"\s+", " ", subject_match.group(1)).strip(" .،:-ـ")
        if subject:
            return f"قرار {subject}"

    return ""


def _legal_group_heading(item_number: int) -> str:
    """Return known folder heading for a numbered item in the uploaded compendium."""

    if 1 <= item_number <= 10:
        return "تفكيك القوانين من (١) إلى (١٠) - المبادئ الدستورية والجنائية"
    if 11 <= item_number <= 20:
        return "تفكيك القوانين من (١١) إلى (٢٠) - التشريعات القضائية والأمنية والاستثمارية"
    return ""


def source_heading_from_document(document: object) -> str:
    """Return the most specific source heading embedded in a retrieved chunk."""

    text = repair_mojibake(str(document or ""))
    law_items = [
        int(match.translate(ARABIC_INDIC_DIGITS))
        for match in LAW_ITEM_PATTERN.findall(text)
    ]
    if law_items:
        inferred = _legal_group_heading(max(law_items))
        if inferred:
            return inferred

    headings = SECTION_SOURCE_PATTERN.findall(text)
    return _clean_source_value(headings[-1]) if headings else ""


def exact_law_sources(
    results: dict,
    registry: dict | None = None,
    limit: int = 1,
) -> list[str]:
    """Return exact source labels from the highest-ranked retrieved chunks."""

    registry = registry or load_registry()
    sources = []
    seen = set()
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    for document in documents:
        section_source = source_heading_from_document(document)
        if section_source and section_source not in seen:
            seen.add(section_source)
            sources.append(section_source)
            if len(sources) >= limit:
                return sources
    if sources:
        return sources

    for document, metadata in zip(documents, metadatas):
        citation = citation_for_metadata(metadata, registry)
        law_name = (
            uploaded_decision_source_label(document)
            if str(metadata.get("source_file", "")).startswith("uploaded_")
            or str(metadata.get("document_upload_id", "")).strip()
            else ""
        ) or display_source_label(metadata, citation)
        law_number = _clean_source_value(citation.get("law_number"))
        law_year = _clean_source_value(citation.get("law_year"))
        article = _clean_source_value(
            citation.get("article_number")
            or citation.get("article")
            or metadata.get("article_reference")
        )

        if not law_name:
            continue

        label = law_name
        if law_number and law_year and law_number not in label:
            label = f"{label} رقم {law_number} لسنة {law_year}"
        elif law_number and law_number not in label:
            label = f"{label} رقم {law_number}"
        elif law_year and law_year not in label:
            label = f"{label} لسنة {law_year}"

        if article:
            label = f"{label}، المادة {article}"

        if label not in seen:
            seen.add(label)
            sources.append(label)
            if len(sources) >= limit:
                break

    return sources


def normalized_answer_text(text: str) -> str:
    """Normalize answer/source text for simple equality checks."""

    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def is_legal_title_only(text: str) -> bool:
    """Return whether the answer is only a legal document title."""

    stripped = answer_body_only(text).strip()
    if "\n" in stripped:
        return False
    return bool(LEGAL_TITLE_ONLY_PATTERN.fullmatch(stripped))


def source_like_answer_labels(results: dict, registry: dict | None = None) -> set[str]:
    """Return source labels that should not appear as the whole answer body."""

    registry = registry or load_registry()
    labels = set()
    for metadata in results.get("metadatas", [[]])[0]:
        citation = citation_for_metadata(metadata, registry)
        for value in (
            citation.get("law_name"),
            citation.get("legal_reference"),
            metadata.get("document_title"),
            metadata.get("legal_reference"),
        ):
            cleaned = _clean_source_value(value)
            if cleaned:
                labels.add(normalized_answer_text(cleaned))
    return labels


def meaningful_answer_from_context(question: str, results: dict) -> str:
    """Extract a concise answer line from retrieved text when the model gives a title."""

    normalized_question = repair_mojibake(question)
    wants_detailed_answer = bool(re.search(r"\b(?:بالتفصيل|تفصيل|تفصيلاً|تفصيلا)\b", normalized_question))
    question_terms = {
        term
        for term in re.findall(r"[\w\u0600-\u06FF]+", normalized_question)
        if len(term) > 2
    }
    wants_law_overview = bool(
        LEGAL_TITLE_ONLY_PATTERN.fullmatch(normalized_question.strip())
        or re.search(
            r"(?:ما\s*هو|ماهو|عرّف|عرف|تعريف)\s+(?:هذا\s+)?قانون",
            normalized_question,
        )
    )
    best_line = ""
    best_score = -1
    prefixes = (
        "المادة",
        "الشرح التفصيلي",
        "الأسباب الموجبة",
        "الهيكل التنظيمي",
        "العنوان",
        "أولًا",
        "أولاً",
        "ثانيًا",
        "ثانياً",
    )

    for document in results.get("documents", [[]])[0]:
        document_text = repair_mojibake(str(document or ""))
        if wants_detailed_answer:
            detailed_answer = detailed_decision_answer_from_context(document_text)
            if detailed_answer:
                return detailed_answer

        for raw_line in document_text.splitlines():
            line = raw_line.strip()
            if not line or source_heading_from_document(line):
                continue
            if LEGAL_TITLE_ONLY_PATTERN.fullmatch(line):
                continue
            if not any(line.startswith(prefix) for prefix in prefixes):
                continue
            content = re.sub(
                r"^(?:المادة\s*\([^)]+\)(?:\s*-\s*[^:]+)?|"
                r"الشرح التفصيلي|الأسباب الموجبة|الهيكل التنظيمي|العنوان)\s*:\s*",
                "",
                line,
            ).strip()
            if not content or LEGAL_TITLE_ONLY_PATTERN.fullmatch(content):
                continue
            line_terms = set(re.findall(r"[\w\u0600-\u06FF]+", line))
            score = len(question_terms & line_terms)
            if wants_law_overview:
                if line.startswith("الأسباب الموجبة"):
                    score += 12
                elif line.startswith("الشرح التفصيلي"):
                    score += 8
                elif line.startswith("المادة"):
                    score -= 2
            else:
                if line.startswith(("أولًا", "أولاً")):
                    score += 8
                if line.startswith(("ثانيًا", "ثانياً")):
                    score += 4
                if line.startswith("المادة"):
                    score += 2
                if "تعريف" in question_terms and line.startswith("المادة"):
                    score += 2
            if score > best_score:
                best_score = score
                best_line = content

    return best_line


def detailed_decision_answer_from_context(context: str) -> str:
    """Return a detailed decision body from retrieved context when available."""

    text = repair_mojibake(context)
    lines = [line.strip() for line in text.splitlines()]
    start_index = None
    for index, line in enumerate(lines):
        if line.startswith(("أولًا", "أولاً")):
            start_index = index
            break
    if start_index is None:
        return ""

    stop_prefixes = (
        "صـور",
        "صورة عنه",
        "د.",
        "الأمين العام",
        "مكتب رئيس",
        "31/12/",
        "18/12/",
    )
    answer_lines = []
    for line in lines[start_index:]:
        if not line:
            if answer_lines and answer_lines[-1]:
                answer_lines.append("")
            continue
        if answer_lines and line.startswith(stop_prefixes):
            break
        answer_lines.append(line)

    answer = "\n".join(answer_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", answer)


def product_price_answer_from_context(question: str, results: dict) -> str:
    """Extract direct product price changes from retrieved legal text."""

    question_text = repair_mojibake(str(question or ""))
    asks_previous_price = bool(re.search(r"(?:كان|سابق|سابقًا|سابقا|قبل)", question_text))
    product_match = re.search(r"سعر\s+منتوج\s+([\u0600-\u06FF\s]+?)(?:\?|؟|$)", question_text)
    if not product_match:
        product_match = re.search(r"منتوج\s+([\u0600-\u06FF\s]+?)(?:\?|؟|$)", question_text)
    if not product_match:
        product_match = re.search(r"سعر\s+([\u0600-\u06FF\s]+?)(?:\?|؟|$)", question_text)
    if not product_match:
        product_match = re.search(r"بشأن\s+([\u0600-\u06FF\s]+?)(?:\?|؟|$)", question_text)
    product = re.sub(r"\s+", " ", product_match.group(1)).strip() if product_match else ""
    product = re.sub(r"\b(?:سابقًا|سابقا|سابق|الآن|حاليًا|حاليا)\b", "", product).strip()
    if product and not product.startswith("زيت"):
        product = product.replace("منتوج", "").strip()
    if not product:
        return ""

    product_terms = {term for term in re.findall(r"[\u0600-\u06FF]+", product) if len(term) > 2}
    price_pattern = re.compile(
        r"منتوج\s+([\u0600-\u06FF\s]+?)\s*\(([^)]+)\)\s*دينار\s*/\s*([^\s.،]+)\s*"
        r"بدل\S*\s+من\s*\(([^)]+)\)\s*دينار\s*/\s*([^\s.،]+)",
    )
    for document in results.get("documents", [[]])[0]:
        text = repair_mojibake(str(document or ""))
        matches = price_pattern.finditer(text)
        for match in matches:
            matched_product, new_price, new_unit, old_price, old_unit = [value.strip() for value in match.groups()]
            matched_terms = set(re.findall(r"[\u0600-\u06FF]+", matched_product))
            if product_terms and not product_terms <= matched_terms:
                continue
            product = matched_product
            break
        else:
            continue
        if asks_previous_price:
            return f"كان سعر منتوج {product} سابقًا {old_price} دينار / {old_unit}."
        return (
            f"تم تعديل سعر منتوج {product} ليصبح {new_price} دينار / {new_unit} "
            f"بدلًا من {old_price} دينار / {old_unit}."
        )
    return ""


def answer_body_only(answer: str) -> str:
    """Remove generated citations, source sections, and old footer text."""

    answer = repair_mojibake(CITATION_PATTERN.sub("", answer or "")).strip()
    if FINAL_WARNING:
        answer = answer.replace(FINAL_WARNING, "").strip()

    body_lines = []
    skip_source_section = False
    for line in answer.splitlines():
        stripped = line.strip()
        normalized = stripped.strip("#*_ ").rstrip(":")
        if normalized in {
            "Analysis / Relevant Legal Sources",
            "Legal Sources",
            "Relevant Legal Sources",
            "المصدر",
            "المصادر",
            "Source",
            "Sources",
        }:
            skip_source_section = True
            continue
        if normalized in {"الجواب", "Answer"}:
            skip_source_section = False
            continue
        if skip_source_section:
            continue
        body_lines.append(line.rstrip())

    body = "\n".join(body_lines).strip()
    return body or INSUFFICIENT_CONTEXT_MESSAGE


def format_legal_sources_section(
    results: dict,
    registry: dict | None = None,
) -> str:
    """Format retrieved legal sources for the required response section."""

    sources = exact_law_sources(results, registry=registry)
    source_text = "\n".join(f"{source}" for source in sources) or "لا توجد مصادر مطابقة"
    return f"Analysis / Relevant Legal Sources\n\n{source_text}"


def format_concise_answer(
    answer: str,
    results: dict,
    registry: dict | None = None,
) -> str:
    """Format the final answer using the required two-section structure."""

    body = answer_body_only(answer)
    return "\n\n".join(
        [
            format_legal_sources_section(results, registry=registry),
            "Answer",
            body,
        ]
    ).strip()


def is_exempt_paragraph(paragraph: str) -> bool:
    """Return whether a paragraph is structural rather than factual."""

    stripped = paragraph.strip()
    normalized_heading = stripped.strip("#*_ ")
    return (
        not stripped
        or bool(SECTION_HEADING_PATTERN.fullmatch(normalized_heading))
        or stripped == INSUFFICIENT_CONTEXT_MESSAGE
        or stripped == FINAL_WARNING
    )


def validate_answer(answer: str, context: str, results: dict) -> list[str]:
    """Validate citations and context-sensitive legal details."""

    errors = []
    answer_without_citations = answer_body_only(answer)
    normalized_body = normalized_answer_text(answer_without_citations)
    if normalized_body in source_like_answer_labels(results):
        errors.append(
            "الإجابة تكرر اسم القانون أو المصدر فقط ولا تتضمن مضمون التعريف أو الحكم."
        )
    if is_legal_title_only(answer_without_citations):
        errors.append(
            "الإجابة هي عنوان قانون فقط؛ يجب استخراج مضمون التعريف أو الحكم من النص."
        )

    answer_without_headings = "\n".join(
        line
        for line in answer_without_citations.splitlines()
        if not SECTION_HEADING_PATTERN.fullmatch(line.strip().strip("#*_ "))
    )

    context_numbers = {
        number.translate(ARABIC_INDIC_DIGITS)
        for number in NUMBER_PATTERN.findall(context)
    }
    # RTL PDF extraction sometimes reverses the stored sequence of digits.
    accepted_context_numbers = context_numbers | {
        number[::-1] for number in context_numbers
    }
    unsupported_numbers = set()
    for number in NUMBER_PATTERN.findall(answer_without_headings):
        normalized_number = number.translate(ARABIC_INDIC_DIGITS)
        if normalized_number not in accepted_context_numbers:
            unsupported_numbers.add(number)
    if unsupported_numbers:
        errors.append(
            "تحتوي الإجابة على أرقام غير موجودة في السياق المسترجع: "
            + "، ".join(sorted(unsupported_numbers))
        )

    for term in PENALTY_STEMS:
        if term in answer_without_headings and term not in context:
            errors.append(
                f"تذكر الإجابة مفهوماً عقابياً من جذر '{term}' "
                "رغم عدم وروده في السياق المسترجع."
            )

    return errors


def ensure_answer_citations(answer: str, results: dict) -> str:
    """Apply the concise answer plus exact law source response format."""

    return format_concise_answer(answer, results)


def related_topics_for_results(question: str, results: dict) -> list[str]:
    """Build simple related follow-up topics from retrieved source text."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    metadata_text = " ".join(
        " ".join(str(value or "") for value in metadata.values())
        for metadata in metadatas
        if isinstance(metadata, dict)
    )
    text = repair_mojibake(" ".join([question, metadata_text, *map(str, documents)]))
    suggestions: list[str] = []

    def add(topic: str) -> None:
        if topic not in suggestions:
            suggestions.append(topic)

    if "قرار" in text or "مجلس الوزراء" in text:
        add("ما رقم القرار وتاريخ صدوره؟")
        add("ما الجهات أو الأطراف المشمولة بالقرار؟")
        add("ما الالتزامات أو الإجراءات المطلوبة لتنفيذه؟")
    if "قانون" in text:
        add("ما نطاق تطبيق هذا القانون؟")
        add("ما أهم الحقوق أو الالتزامات الواردة فيه؟")
        add("هل توجد عقوبات أو استثناءات مرتبطة بالموضوع؟")
    if "كتاب" in text:
        add("ما رقم وتاريخ الكتاب الذي استندت إليه الوثيقة؟")
    if re.search(r"مبلغ|دينار|دولار|سعر|كلفة|تكلفة", text):
        add("ما المبلغ أو السعر المذكور وبأي عملة؟")
    return (suggestions or [
        "ما أهم النقاط العملية في هذه الوثيقة؟",
        "ما الجهة المسؤولة أو المعنية بالموضوع؟",
        "ما المعلومات الناقصة التي تحتاج إلى تحقق من المصدر؟",
    ])[:3]


def _trim_topic_value(value: str, limit: int = 70) -> str:
    value = re.sub(r"\s+", " ", repair_mojibake(str(value or ""))).strip(" .،؛:")
    return value[:limit].rstrip(" .،؛:")


def _topic_entity_candidates(text: str) -> list[str]:
    pattern = re.compile(
        r"\b(?:وزارة|شركة|مجلس|هيئة|دائرة|محافظة|لجنة)\s+[\u0600-\u06FF\s]{2,55}",
    )
    entities = []
    for match in pattern.finditer(text):
        entity = _trim_topic_value(re.split(r"[،؛:.\n\r]", match.group(0), 1)[0])
        if entity and entity not in entities:
            entities.append(entity)
    return entities


def related_topics_for_results(question: str, results: dict) -> list[str]:
    """Build related topics from facts found in the same retrieved legal text."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    metadata_text = " ".join(
        " ".join(str(value or "") for value in metadata.values())
        for metadata in metadatas
        if isinstance(metadata, dict)
    )
    text = repair_mojibake(" ".join([metadata_text, *map(str, documents)]))
    suggestions: list[str] = []

    def add(topic: str) -> None:
        if topic not in suggestions:
            suggestions.append(topic)

    book = re.search(
        r"كتاب\s+(.{0,80}?)\s+المرقم\s+بالعدد\s*\(\s*([^)]+?)\s*\)\s+المؤرخ\s+في\s+([0-9٠-٩/\\-]+)",
        text,
        flags=re.DOTALL,
    )
    if book:
        issuer, number, date = [_trim_topic_value(value) for value in book.groups()]
        issuer_text = f" {issuer}" if issuer else ""
        add(f"هل تريد معرفة أثر كتاب{issuer_text} المرقم ({number}) المؤرخ في {date}؟")

    amount = re.search(r"([0-9٠-٩][0-9٠-٩.,/ ]+)\s*(دينار|دولار)", text)
    if amount:
        value, currency = [_trim_topic_value(value) for value in amount.groups()]
        add(f"أستطيع مساعدتك في توضيح تفاصيل المبلغ {value} {currency} الوارد في النص.")

    date = re.search(r"\b([0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{1,2}\s*/\s*[0-9٠-٩]{4})\b", text)
    if date:
        add(f"هل تريد معرفة دلالة تاريخ {date.group(1)} في هذه الوثيقة؟")

    clause = re.search(r"\b(أولاً|أولًا|ثانياً|ثانيًا|ثالثاً|ثالثًا)\s*[:：]?\s*(.{10,90})", text)
    if clause:
        label = _trim_topic_value(clause.group(1))
        add(f"هل تريد أن أشرح لك البند {label} الوارد في النص؟")

    for entity in _topic_entity_candidates(text)[:2]:
        add(f"أستطيع مساعدتك في توضيح دور {entity} في النص.")

    return (suggestions or [
        "هل تريد معرفة النقطة القانونية الرئيسية التي يقررها هذا النص؟",
        "أستطيع مساعدتك في تحديد العبارة الأهم المرتبطة بسؤالك من نفس النص.",
        "هل تريد أن أراجع لك الجزء الذي يحتاج إلى قراءة تفصيلية من نفس الوثيقة؟",
    ])[:3]


def append_related_topics(answer: str, question: str, results: dict) -> str:
    """Append related topics after validation so they do not affect grounding checks."""

    if (
        not answer
        or RELATED_TOPICS_HEADING in answer
        or "مواضيع مقترحة:" in answer
        or INSUFFICIENT_CONTEXT_MESSAGE in answer
    ):
        return answer
    topics = related_topics_for_results(question, results)
    topic_lines = "\n".join(f"- {topic}" for topic in topics)
    return f"{answer.strip()}\n\n{RELATED_TOPICS_HEADING}\n{topic_lines}"


def answer_result_with_related_topics(result: AnswerResult, question: str, results: dict) -> AnswerResult:
    """Append related topics to a direct answer result."""

    return AnswerResult(
        content=append_related_topics(result.content, question, results),
        warnings=result.warnings,
    )


def repair_empty_or_title_answer(question: str, answer: str, results: dict) -> str:
    """Replace title-only answers with a direct line from retrieved context."""

    body = answer_body_only(answer)
    if not is_legal_title_only(body):
        return body
    fallback = product_price_answer_from_context(question, results) or meaningful_answer_from_context(question, results)
    return fallback or INSUFFICIENT_CONTEXT_MESSAGE


def registry_metadata_warnings(results: dict, registry: dict) -> list[str]:
    """Return Arabic warnings for incomplete registry-backed legal metadata."""

    warnings = []
    for metadata in results.get("metadatas", [[]])[0]:
        chunk_id = chunk_id_for(metadata) or "missing"
        citation = citation_for_metadata(metadata, registry)
        missing = [
            field
            for field in ("law_year", "law_name")
            if not str(citation.get(field, "")).strip()
        ]
        if missing:
            warnings.append(
                "بيانات الاستشهاد ناقصة للمقطع "
                f"'{chunk_id}': " + "، ".join(missing)
            )
    return warnings


def _retrieved_documents_for_source(results: dict, source_file: str) -> list[str]:
    """Return retrieved documents belonging to one source file."""

    try:
        from .chunk_text import CHUNKS_FILE
    except ImportError:
        from chunk_text import CHUNKS_FILE
    source_text = _source_text_for_source_file(source_file)
    if source_text:
        return [source_text]
    return []


def _source_keys_from_payload(payload: dict, path: Path) -> set[str]:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    keys = {
        path.name,
        path.stem,
        str(payload.get("id") or ""),
        str(payload.get("source_file") or ""),
        str(payload.get("source") if not isinstance(payload.get("source"), dict) else ""),
        str(payload.get("original_filename") or ""),
        str(source.get("filename") or ""),
        str(source.get("source_file") or ""),
        str(metadata.get("source_filename") or ""),
        str(metadata.get("document_id") or ""),
    }
    cleaned = set()
    for key in keys:
        value = _clean_source_value(key)
        if value:
            cleaned.add(value)
            cleaned.add(Path(value).name)
            cleaned.add(Path(value).stem)
    return cleaned


def _source_text_for_source_file(source_file: str) -> str:
    """Return full JSON source text for a retrieved best document."""

    source_keys = {
        _clean_source_value(source_file),
        Path(_clean_source_value(source_file)).name,
        Path(_clean_source_value(source_file)).stem,
    }
    source_keys = {key for key in source_keys if key}
    if not source_keys:
        return ""

    try:
        from .config import PROJECT_ROOT
    except ImportError:
        from config import PROJECT_ROOT

    for folder in SOURCE_JSON_DIRS:
        root = PROJECT_ROOT / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            if not (source_keys & _source_keys_from_payload(payload, path)):
                continue
            text = source_text_from_payload(payload)
            if text:
                return repair_mojibake(text)
    return ""


def _source_text_for_json_path(json_path: object) -> str:
    """Return full source text from an explicit JSON path when it is local."""

    path_text = _clean_source_value(json_path)
    if not path_text:
        return ""
    try:
        from .config import PROJECT_ROOT
    except ImportError:
        from config import PROJECT_ROOT

    candidates = [Path(path_text)]
    if not Path(path_text).is_absolute():
        candidates.append(PROJECT_ROOT / path_text)
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            continue
        if not resolved.exists() or resolved.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            text = source_text_from_payload(payload)
            if text:
                return repair_mojibake(text)
    return ""


def _source_text_for_metadata(metadata: dict) -> str:
    """Resolve complete source text from original JSON metadata, never from Chroma text."""

    json_text = _source_text_for_json_path(metadata.get("json_path") or metadata.get("original_json_path"))
    if json_text:
        return json_text
    for value in (
        metadata.get("document_id"),
        metadata.get("source_filename"),
        metadata.get("source_file"),
    ):
        text = _source_text_for_source_file(str(value or ""))
        if text:
            return text
    return ""


def _is_routing_or_cover_page(text: str) -> bool:
    """Return whether extracted text is only a forwarding/copy-routing page."""

    normalized = normalized_answer_text(repair_mojibake(text))
    has_routing = any(
        marker in normalized
        for marker in (
            "صورة عنه الى",
            "صورة عنه إلى",
            "للاطلاع مع التقدير",
            "ربطا قراري مجلس الوزراء للاطلاع",
            "المرافقات قرار مجلس الوزراء",
        )
    )
    has_substantive_decision = any(
        marker in normalized
        for marker in (
            "قرر مجلس الوزراء",
            "قررر مجلس الوزراء",
            "بناء على ما عرضته",
            "اولا الموافقة",
            "أولا الموافقة",
            "ثانيا تتحمل",
            "ثانيًا تتحمل",
        )
    )
    return has_routing and not has_substantive_decision


def _substantive_decision_documents(documents: list[str]) -> list[str]:
    """Keep only chunks that contain the actual decision body."""

    substantive = []
    for document in documents:
        if _is_routing_or_cover_page(document):
            continue
        normalized = normalized_answer_text(repair_mojibake(document))
        if any(
            marker in normalized
            for marker in (
                "قرر مجلس الوزراء",
                "قررر مجلس الوزراء",
                "بناء على ما عرضته",
                "اولا الموافقة",
                "أولا الموافقة",
                "ثانيا تتحمل",
                "ثانيًا تتحمل",
            )
        ):
            substantive.append(document)
    return substantive


def _format_complete_source_text(text: str) -> str:
    """Make extracted government-decision text readable without summarizing it."""

    text = repair_mojibake(str(text or ""))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    start_patterns = (
        r"بناء\s*[ًا]*\s+على",
        r"بنا\s*[ءاً]*\s+على",
        r"ق\s*ـ*\s*ر\s*ر\s+مجلس\s+الوزراء",
        r"قرر\s+مجلس\s+الوزراء",
    )
    start_positions = [
        match.start()
        for pattern in start_patterns
        for match in [re.search(pattern, text)]
        if match
    ]
    if start_positions:
        text = text[min(start_positions) :].strip()

    footer_match = re.search(
        r"(?:\bد\.\s*)?حميد\s+نعيم\s+الغز[يي].*|"
        r"الأمين\s+العام\s+لمجلس\s+الوزراء.*|"
        r"ا(?:ل)?أمين\s+العام\s+لمجلس\s+الوزراء.*",
        text,
    )
    if footer_match:
        text = text[: footer_match.start()].strip()

    text = re.sub(r"\s*•\s*", "\n• ", text)
    text = re.sub(r"\s+([:،؛.])", r"\1", text)
    text = re.sub(r"(\))\s+([،.])", r"\1\2", text)
    text = re.sub(r"\s+(أولاً|أولًا|ثانياً|ثانيًا|ثالثاً|ثالثًا)\s*[:：]", r"\n• \1:", text)
    text = re.sub(r"\s+([0-9٠-٩]+)\s*[.)-]\s+", r"\n\1. ", text)
    return text.strip()


def _looks_like_government_decision(text: str) -> bool:
    """Return whether retrieved text appears to be a Cabinet decision."""

    normalized = normalized_answer_text(repair_mojibake(text))
    has_cabinet = "مجلس الوزراء" in normalized or (
        "مجلس" in normalized and "وزراء" in normalized
    )
    has_decision_details = any(
        marker in normalized
        for marker in ("قرر", "قرار", "اولا", "أولا", "ثانيا", "ثانيًا", "المادة")
    )
    return has_cabinet and has_decision_details


def complete_uploaded_source_answer(answer: str, results: dict) -> str:
    """Keep uploaded Word/doc answers concise instead of expanding to full text."""

    return answer


def _required_query_markers(question: str) -> list[str]:
    """Return exact identifiers that must appear in retrieved context."""

    repaired = repair_mojibake(question)
    markers = []
    markers.extend(re.findall(r"\b[A-Z]{2,}(?:-[0-9A-Z]+)?\b", repaired))
    markers.extend(re.findall(r"\b\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}\b", repaired))
    markers.extend(re.findall(r"\b\d{1,3}(?:\.\d{3})+(?:\.\d+)?\b", repaired))
    for phrase in (
        "الثالثة والخمسين",
        "الطائرات المروحية",
        "وزارة الدفاع",
        "عقد تصليح",
    ):
        if phrase in repaired:
            markers.append(phrase)
    return list(dict.fromkeys(markers))


def _marker_variants(marker: str) -> set[str]:
    marker = repair_mojibake(marker).strip()
    normalized_marker = re.sub(r"[\u0640ـ]+", "", marker)
    variants = {
        marker,
        normalized_marker,
        re.sub(r"\s+", " ", marker),
        re.sub(r"\s+", " ", normalized_marker),
    }
    if "/" in marker:
        variants.add(re.sub(r"\s*/\s*", "/", marker))
        variants.add(re.sub(r"\s*/\s*", " / ", marker))
    if "-" in marker:
        variants.add(marker.replace("-", ""))
        variants.add(marker.replace("-", " "))
    return {value.strip().lower() for value in variants if value.strip()}


def missing_required_query_markers(question: str, context: str) -> list[str]:
    """Return exact query identifiers not found in retrieved context."""

    context_text = repair_mojibake(context).lower()
    normalized_context_text = re.sub(r"[\u0640ـ]+", "", context_text)
    compact_context = re.sub(r"\s+", " ", context_text)
    normalized_compact_context = re.sub(r"\s+", " ", normalized_context_text)
    missing = []
    for marker in _required_query_markers(question):
        if not any(
            variant in context_text
            or variant in compact_context
            or variant in normalized_context_text
            or variant in normalized_compact_context
            for variant in _marker_variants(marker)
        ):
            missing.append(marker)
    return missing


def call_chat_model(
    messages: list[dict],
    status_callback: Callable[[str], None] | None = None,
) -> str:
    """Stream a model response while retaining it for validation."""

    try:
        from .runtime_settings import runtime_settings
    except ImportError:
        from runtime_settings import runtime_settings
    model_settings = runtime_settings()["model"]
    active_client = ollama.Client(
        host=model_settings["ollama_base_url"],
        timeout=model_settings["request_timeout"],
    )
    response_stream = active_client.chat(
        model=model_settings["chat_model"],
        messages=messages,
        stream=True,
        keep_alive=model_settings["keep_alive"],
        options={
            "temperature": model_settings["temperature"],
            "top_p": model_settings["top_p"],
            "num_ctx": model_settings["context_length"],
            "num_predict": model_settings["max_answer_tokens"],
        },
    )
    response_parts = []
    last_progress_at = time.perf_counter()

    for response_part in response_stream:
        content = response_part["message"]["content"]
        if content:
            response_parts.append(content)

        now = time.perf_counter()
        if status_callback and now - last_progress_at >= 10:
            character_count = sum(len(part) for part in response_parts)
            status_callback(
                f"النموذج ما زال يعمل... تم توليد {character_count} حرفاً."
            )
            last_progress_at = now

    return "".join(response_parts).strip()


def generate_answer(
    question: str,
    results: dict,
    status_callback: Callable[[str], None] | None = None,
) -> AnswerResult:
    """Generate a grounded answer with the configured Ollama chat model."""

    def report(message: str) -> None:
        if status_callback:
            status_callback(message)

    registry = load_registry()
    results, registry_filter_warnings = filter_results_to_registered(
        results,
        registry=registry,
    )
    log_retrieval_results(question, results)
    initial_metadata = _top_metadata(results)
    initial_long_text = _source_text_for_metadata(initial_metadata) if initial_metadata else ""
    log_long_text_status(
        initial_metadata,
        bool(initial_long_text),
        "Full document available" if initial_long_text else "Full document not loaded",
        len(initial_long_text),
    )
    unusable_answer = unusable_source_text_answer(results)
    if unusable_answer:
        log_answer_generation(NO_USABLE_LEGAL_SOURCE_TEXT)
        return unusable_answer
    direct_decision_number_answer = decision_number_answer(question, results)
    if direct_decision_number_answer:
        log_answer_generation("direct decision-number answer")
        return answer_result_with_related_topics(direct_decision_number_answer, question, results)
    direct_document_date_answer = document_date_answer(question, results)
    if direct_document_date_answer:
        log_answer_generation("direct document-date answer")
        return answer_result_with_related_topics(direct_document_date_answer, question, results)
    direct_recommendation_number_answer = recommendation_number_answer(question, results)
    if direct_recommendation_number_answer:
        log_answer_generation("direct recommendation-number answer")
        return answer_result_with_related_topics(direct_recommendation_number_answer, question, results)
    direct_source_book_answer = source_book_answer(question, results)
    if direct_source_book_answer:
        log_answer_generation("direct source-book answer")
        return answer_result_with_related_topics(direct_source_book_answer, question, results)
    direct_full_text_answer = full_document_text_answer(question, results)
    if direct_full_text_answer:
        log_answer_generation("direct full-document text answer")
        return direct_full_text_answer
    if wants_full_document_context(question):
        results = results_with_full_document_context(results)
    metadata_warnings = registry_metadata_warnings(results, registry)
    context = build_context(results, registry=registry)
    if not context:
        return AnswerResult(
            content=format_concise_answer(
                INSUFFICIENT_CONTEXT_MESSAGE,
                results,
                registry=registry,
            ),
            warnings=registry_filter_warnings,
        )
    missing_markers = missing_required_query_markers(question, context)
    if missing_markers:
        return AnswerResult(
            content=format_concise_answer(
                INSUFFICIENT_CONTEXT_MESSAGE,
                {"documents": [[]], "metadatas": [[]]},
                registry=registry,
            ),
            warnings=(
                registry_filter_warnings
                + metadata_warnings
                + [
                    "لم تظهر المعرفات الدقيقة المطلوبة في المصادر المسترجعة: "
                    + "، ".join(missing_markers)
                ]
            ),
        )

    report("جارٍ توليد الإجابة من المقاطع المسترجعة...")
    log_answer_generation("model generation started")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context)},
    ]
    raw_answer = repair_empty_or_title_answer(
        question,
        call_chat_model(messages, status_callback=status_callback),
        results,
    )
    raw_answer = complete_uploaded_source_answer(raw_answer, results)
    answer = ensure_answer_citations(raw_answer, results)
    log_answer_generation("model generation completed")
    validation_errors = validate_answer(answer, context, results)

    if validation_errors:
        report("جارٍ تصحيح الاستشهادات في الإجابة...")
        messages.extend(
            [
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": build_correction_prompt(
                        answer,
                        validation_errors,
                    ),
                },
            ]
        )
        first_answer = answer
        first_validation_errors = validation_errors
        try:
            raw_answer = repair_empty_or_title_answer(
                question,
                call_chat_model(messages, status_callback=status_callback),
                results,
            )
            raw_answer = complete_uploaded_source_answer(raw_answer, results)
            answer = ensure_answer_citations(raw_answer, results)
        except httpx.TimeoutException:
            return AnswerResult(
                content=first_answer,
                warnings=(
                    registry_filter_warnings
                    + metadata_warnings
                    + first_validation_errors
                    + [
                        "انتهت مهلة محاولة تصحيح الاستشهادات؛ "
                        "تم عرض الإجابة الأولية بدلاً من فقدانها."
                    ]
                ),
            )
        validation_errors = validate_answer(answer, context, results)

    warnings = list(
        dict.fromkeys(
            registry_filter_warnings + metadata_warnings + validation_errors
        )
    )
    answer = append_related_topics(answer, question, results)
    return AnswerResult(content=answer, warnings=warnings)


def print_vetting_warnings(warnings: list[str]) -> None:
    """Print citation-vetting warnings below a terminal answer."""

    if not warnings:
        return

    print()
    print("تحذيرات التحقق من الاستشهادات:")
    for warning in warnings:
        print(f"- {warning}")


def main() -> None:
    """Retrieve legal context and generate one grounded Arabic answer."""

    try:
        question = get_question()
        quick_response = get_quick_response(question)
        if quick_response:
            print()
            print(quick_response)
            return

        exact_answer = answer_exact_law(question)
        if exact_answer:
            print()
            print(exact_answer["answer"])
            return

        started_at = time.perf_counter()

        print("جارٍ تحويل السؤال إلى تمثيل متجهي والبحث في الفهرس...", flush=True)
        results = search(question)
        retrieval_seconds = time.perf_counter() - started_at
        result_count = len(results.get("documents", [[]])[0])
        print(
            f"تم استرجاع {result_count} مقاطع خلال "
            f"{retrieval_seconds:.1f} ثانية.",
            flush=True,
        )

        if retrieved_context_debug:
            print_retrieved_context(build_context(results))

        answer_result = generate_answer(
            question,
            results,
            status_callback=lambda message: print(message, flush=True),
        )

        print()
        print(answer_result.content)
        print_vetting_warnings(answer_result.warnings)
    except (EOFError, KeyboardInterrupt):
        print("\nتم إلغاء العملية.")
        sys.exit(1)
    except ValueError as error:
        print(f"تعذر إنشاء الإجابة: {error}")
        sys.exit(1)
    except NotFoundError:
        print(
            f"تعذر إنشاء الإجابة: المجموعة '{COLLECTION_NAME}' غير موجودة. "
            "شغّل python app/build_index.py أولاً."
        )
        sys.exit(1)
    except ConnectionError:
        print("تعذر الاتصال بخدمة Ollama. تأكد من تشغيلها.")
        sys.exit(1)
    except httpx.TimeoutException:
        print(
            "انتهت مهلة طلب Ollama بعد "
            f"{OLLAMA_REQUEST_TIMEOUT_SECONDS} ثانية. "
            "تحقق من موارد الجهاز أو استخدم نموذجاً أصغر."
        )
        sys.exit(1)
    except ollama.ResponseError as error:
        print(f"فشل طلب Ollama: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"تعذر إنشاء الإجابة: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
