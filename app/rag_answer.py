"""Answer Arabic legal questions using only retrieved local context."""

import argparse
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

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
    from .ollama_client import client as ollama_client
    from .prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
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
    from ollama_client import client as ollama_client
    from prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
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
        or "مصدر غير معروف"
    ).strip()


def build_context(results: dict, registry: dict | None = None) -> str:
    """Format retrieved chunks with registry-backed legal citation metadata."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    registry = registry or load_registry()
    context_sections = []

    for rank, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        citation = citation_for_metadata(metadata, registry)
        source_file = repair_mojibake(citation_source_label(metadata, registry))
        page_number = metadata.get("page_number", "غير معروف")
        legal_reference = repair_mojibake(str(metadata.get("legal_reference", "")))
        document_title = repair_mojibake(str(metadata.get("document_title", "")))
        document_type = repair_mojibake(str(metadata.get("document_type", "")))
        classification = (
            citation.get("classification")
            or metadata.get("document_classification")
            or document_type
        )
        metadata_lines = [
            f"المصدر: {source_file}",
            f"الصفحة: {page_number}",
            f"chunk_id: {chunk_id_for(metadata) or 'missing'}",
            f"law_number: {citation.get('law_number') or 'missing'}",
            f"law_year: {citation.get('law_year') or 'missing'}",
            f"article_number: {citation.get('article_number') or 'missing'}",
            f"law_name: {citation.get('law_name') or 'missing'}",
            f"classification: {classification or 'missing'}",
        ]
        if document_type:
            metadata_lines.append(f"نوع الوثيقة: {document_type}")
        if document_title:
            metadata_lines.append(f"عنوان الوثيقة: {document_title}")
        if legal_reference:
            metadata_lines.append(f"المرجع القانوني: {legal_reference}")
        context_sections.append(
            "\n".join(
                [
                    f"[المقطع {rank}]",
                    *metadata_lines,
                    "النص:",
                    repair_mojibake(document),
                ]
            )
        )

    return "\n\n".join(context_sections)

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
        law_name = _clean_source_value(
            citation.get("law_name")
            or citation.get("legal_reference")
            or metadata.get("section_title")
            or metadata.get("document_title")
            or metadata.get("legal_reference")
            or metadata.get("source_file")
        )
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
    )

    for document in results.get("documents", [[]])[0]:
        for raw_line in repair_mojibake(str(document or "")).splitlines():
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
                if line.startswith("المادة"):
                    score += 2
                if "تعريف" in question_terms and line.startswith("المادة"):
                    score += 2
            if score > best_score:
                best_score = score
                best_line = content

    return best_line


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
    source_text = "\n".join(f"{source}" for source in sources) or "Not specified"
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


def repair_empty_or_title_answer(question: str, answer: str, results: dict) -> str:
    """Replace title-only answers with a direct line from retrieved context."""

    body = answer_body_only(answer)
    if not is_legal_title_only(body):
        return body
    fallback = meaningful_answer_from_context(question, results)
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

    report("جارٍ توليد الإجابة من المقاطع المسترجعة...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context)},
    ]
    raw_answer = repair_empty_or_title_answer(
        question,
        call_chat_model(messages, status_callback=status_callback),
        results,
    )
    answer = ensure_answer_citations(raw_answer, results)
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
