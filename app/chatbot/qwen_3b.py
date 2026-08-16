"""Use the indexed documents with the Qwen 3B chatbot."""

from app.citation_registry import filter_results_to_registered, load_registry
from app.config import CHAT_MODEL
from app.prompts import INSUFFICIENT_CONTEXT_MESSAGE
from app.rag_answer import (
    AnswerResult,
    format_concise_answer,
    generate_answer,
    get_quick_response,
    meaningful_answer_from_context,
)
from app.search_index import search


QWEN_3B_MODEL = CHAT_MODEL


def is_insufficient_answer(content: str) -> bool:
    """Return whether the chatbot answer says the retrieved context is insufficient."""

    return (
        INSUFFICIENT_CONTEXT_MESSAGE in content
        or "لا تحتوي المصادر القانونية المسترجعة" in content
        or "لم تحتوي المصادر القانونية المسترجعة" in content
        or "لم يحتوي المصادر القانونية المسترجعة" in content
    )


def answer_with_qwen_3b(question: str) -> AnswerResult:
    """Answer one question using ChromaDB retrieval and the Qwen 3B chatbot."""

    quick_response = get_quick_response(question)
    if quick_response:
        return AnswerResult(content=quick_response, warnings=[])

    results = search(question)
    registry = load_registry()
    validated_results, registry_warnings = filter_results_to_registered(
        results,
        registry=registry,
    )
    answer = generate_answer(question, validated_results)
    if is_insufficient_answer(answer.content):
        fallback = meaningful_answer_from_context(question, validated_results)
        if fallback:
            return AnswerResult(
                content=format_concise_answer(fallback, validated_results, registry=registry),
                warnings=list(dict.fromkeys(registry_warnings + answer.warnings)),
            )
    return AnswerResult(
        content=answer.content,
        warnings=list(dict.fromkeys([*registry_warnings, *answer.warnings])),
    )
