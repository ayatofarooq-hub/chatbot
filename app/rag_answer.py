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
    from .config import (
        CHAT_MAX_TOKENS,
        CHAT_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
        retrieved_context_debug,
    )
    from .ollama_client import client as ollama_client
    from .prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
    )
    from .search_index import search
except ImportError:
    # Support direct execution with: python app/rag_answer.py
    from build_index import COLLECTION_NAME
    from config import (
        CHAT_MAX_TOKENS,
        CHAT_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
        retrieved_context_debug,
    )
    from ollama_client import client as ollama_client
    from prompts import (
        FINAL_WARNING,
        INSUFFICIENT_CONTEXT_MESSAGE,
        SYSTEM_PROMPT,
        build_correction_prompt,
        build_user_prompt,
    )
    from search_index import search


CITATION_PATTERN = re.compile(
    r"\[المصدر:\s*(.+?)،\s*الصفحة:\s*([0-9٠-٩]+)\]"
)
NUMBER_PATTERN = re.compile(r"[0-9٠-٩]+")
SECTION_HEADING_PATTERN = re.compile(
    r"^\s*[1-4١-٤][.)-]?\s*"
    r"(خلاصة مختصرة|التفاصيل القانونية ذات الصلة|"
    r"ملاحظات لصانع القرار|المصادر)\s*:?\s*$"
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

    if normalized_question in GREETING_WORDS:
        return "مرحباً، كيف يمكنني مساعدتك في سؤالك القانوني العراقي؟"

    if normalized_question in THANKS_WORDS:
        return "على الرحب والسعة."

    return None


def build_context(results: dict) -> str:
    """Format retrieved chunks with citation metadata for the chat model."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    context_sections = []

    for rank, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        source_file = metadata.get("source_file", "غير معروف")
        page_number = metadata.get("page_number", "غير معروف")
        context_sections.append(
            "\n".join(
                [
                    f"[المقطع {rank}]",
                    f"المصدر: {source_file}",
                    f"الصفحة: {page_number}",
                    "النص:",
                    document,
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


def get_allowed_citations(results: dict) -> set[tuple[str, str]]:
    """Return valid source and page pairs from the retrieved results."""

    metadatas = results.get("metadatas", [[]])[0]
    return {
        (str(metadata.get("source_file")), str(metadata.get("page_number")))
        for metadata in metadatas
    }


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
    allowed_citations = get_allowed_citations(results)
    paragraphs = re.split(r"\n\s*\n", answer.strip())

    for paragraph_number, paragraph in enumerate(paragraphs, start=1):
        if is_exempt_paragraph(paragraph):
            continue

        citations = CITATION_PATTERN.findall(paragraph)
        if not citations:
            errors.append(
                f"الفقرة {paragraph_number} لا تحتوي على استشهاد."
            )
            continue

        for source_file, page_number in citations:
            if (source_file.strip(), page_number) not in allowed_citations:
                errors.append(
                    f"الفقرة {paragraph_number} تستخدم مصدراً أو صفحة غير مسترجعة."
                )

    answer_without_citations = CITATION_PATTERN.sub("", answer)
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

    if not answer.rstrip().endswith(FINAL_WARNING):
        errors.append("التحذير الختامي الإلزامي مفقود أو غير مطابق.")

    return errors


def call_chat_model(
    messages: list[dict],
    status_callback: Callable[[str], None] | None = None,
) -> str:
    """Stream a model response while retaining it for validation."""

    response_stream = ollama_client.chat(
        model=CHAT_MODEL,
        messages=messages,
        stream=True,
        keep_alive=OLLAMA_KEEP_ALIVE,
        options={
            "temperature": 0,
            "num_predict": CHAT_MAX_TOKENS,
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

    context = build_context(results)
    if not context:
        return AnswerResult(
            content=f"{INSUFFICIENT_CONTEXT_MESSAGE}\n\n{FINAL_WARNING}",
            warnings=[],
        )

    report("جارٍ توليد الإجابة من المقاطع المسترجعة...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context)},
    ]
    answer = call_chat_model(messages, status_callback=status_callback)
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
        answer = call_chat_model(messages, status_callback=status_callback)
        validation_errors = validate_answer(answer, context, results)

    return AnswerResult(content=answer, warnings=validation_errors)


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
