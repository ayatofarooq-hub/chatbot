"""Diagnostic search for testing retrieval quality in the legal index."""

import argparse
import json
import math
import re
import sys
from pathlib import Path

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError

try:
    from .arabic_search import normalize_arabic_for_search, tokenize_arabic_search
    from .build_index import COLLECTION_NAME
    from .chunk_text import CHUNKS_FILE
    from .config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from .ollama_client import client as ollama_client
    from .retrieval_logging import log_retrieval_results
    from .text_encoding import repair_json_text
except ImportError:
    # Support direct execution with: python app/search_index.py
    from arabic_search import normalize_arabic_for_search, tokenize_arabic_search
    from build_index import COLLECTION_NAME
    from chunk_text import CHUNKS_FILE
    from config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from ollama_client import client as ollama_client
    from retrieval_logging import log_retrieval_results
    from text_encoding import repair_json_text


RESULT_COUNT = 5
CANDIDATE_COUNT = 30
LEXICAL_CANDIDATE_COUNT = 80
METADATA_CANDIDATE_COUNT = 80
AGGREGATE_RESULT_COUNT = 10
TEXT_PREVIEW_LENGTH = 500
STOP_WORDS = {
    "اجابه",
    "اريد",
    "الجريمه",
    "القانون",
    "العقوبه",
    "إلى",
    "الى",
    "أو",
    "او",
    "عن",
    "على",
    "في",
    "جريمه",
    "رقم",
    "سنه",
    "عقوبه",
    "قانون",
    "لسنه",
    "ما",
    "ماهي",
    "من",
    "هل",
    "هو",
    "هي",
    "و",
}
DATE_PATTERN = re.compile(r"\b\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}\b")
BOOK_NUMBER_PATTERN = re.compile(r"\b\d{1,5}\s*/\s*\d{1,5}(?:\s*/\s*\d{2,4})?\b")
NUMBER_PATTERN = re.compile(r"\b\d{1,6}(?:\.\d{3})*(?:\.\d+)?\b")
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
SUMMARY_ONLY_LABEL_PATTERN = re.compile(
    r"^\s*(?:summary|ملخص|الملخص|الخلاصة|الشرح التفصيلي|الشرح التفصيلى)\s*[:：\-]?",
    re.IGNORECASE | re.MULTILINE,
)
SUMMARY_ONLY_MARKERS = ("الشرح التفصيلي", "الشرح التفصيلى", "summary")
ORIGINAL_SOURCE_MARKERS = (
    "قرر مجلس الوزراء",
    "قــرر مجلس الوزراء",
    "قــرّر مجلس الوزراء",
    "المنعقدة في",
    "المرقم بالعدد",
    "بناءً على",
    "بناء على",
    "استناداً إلى",
    "استنادا إلى",
)
STRONG_ARABIC_PHRASE_PATTERNS = (
    re.compile(r"(?:وزارة|وزاره)\s+[\u0600-\u06ff ]{2,40}"),
    re.compile(r"شركة\s+[\u0600-\u06ff0-9 ]{2,50}"),
    re.compile(r"(?:السيد|الدكتور|د\.|الاستاذ)\s+[\u0600-\u06ff ]{2,40}"),
    re.compile(r"(?:منتوج|مادة|ماده)\s+[\u0600-\u06ff ]{2,40}"),
    re.compile(r"زيت\s+[\u0600-\u06ff ]{2,25}"),
    re.compile(r"مجلس\s+الوزراء(?:\s+العراقي)?"),
)
QUERY_INTENT_TERMS = {
    "source_book": (
        "كتاب",
        "اعتمد",
        "استند",
        "استناد",
        "بناء",
        "المرقم بالعدد",
        "المؤرخ في",
        "رقم كتاب",
        "تاريخ كتاب",
    ),
    "amount": (
        "مبلغ",
        "بمبلغ",
        "مقداره",
        "دينار",
        "دولار",
        "سعر",
        "كلفة",
        "تكلفة",
        "اصبح",
        "بدلا من",
    ),
    "date": (
        "تاريخ",
        "متى",
        "صدر",
        "صدور",
        "المؤرخ",
        "جلسة",
        "انعقاد",
    ),
    "decision_number": (
        "رقم القرار",
        "قرار مجلس الوزراء",
        "رقم قرار",
        "قرر مجلس الوزراء",
    ),
    "responsibility": (
        "جهة",
        "مسؤول",
        "مسؤولة",
        "تتحمل",
        "تنفذ",
        "تنفيذ",
        "وزارة",
        "شركة",
        "لجنة",
    ),
    "summary": (
        "مضمون",
        "محتوى",
        "ملخص",
        "خلاصة",
        "ما الذي قرر",
        "ماذا قرر",
        "الموافقة",
    ),
}

QUERY_INTENT_EXPANSIONS = {
    "source_book": "كتاب المرقم بالعدد المؤرخ في بناء على استنادا الى استنادا إلى اعتمد عليه",
    "amount": "مبلغ بمبلغ مقداره مقدار دينار دولار سعر كلفة تكلفة اصبح بدلا من",
    "date": "تاريخ المؤرخ في صدر صدور جلسة انعقاد تاريخ صدور القرار تاريخ انعقاد الجلسة",
    "decision_number": "رقم القرار رقم قرار مجلس الوزراء قرر مجلس الوزراء decision_number",
    "responsibility": "الجهة المسؤولة تتحمل تنفيذ تنفذ وزارة شركة لجنة الالتزامات الاجراءات",
    "summary": "مضمون محتوى ملخص خلاصة قرر مجلس الوزراء الموافقة اولا ثانيا",
}


def get_question() -> str:
    """Read a question from a command argument or an interactive prompt."""

    parser = argparse.ArgumentParser(
        description="Search the Iraqi legal ChromaDB index."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Arabic legal question to search for.",
    )
    arguments = parser.parse_args()

    question = " ".join(arguments.question).strip()
    if not question:
        question = input("Enter an Arabic legal question: ").strip()

    if not question:
        raise ValueError("The question cannot be empty.")

    return question


def normalize_for_search(text: str) -> str:
    """Normalize Arabic variants for ranking without changing indexed text."""

    return normalize_arabic_for_search(text)


def is_summary_only_chunk_text(text: str) -> bool:
    """Detect chunks that are generated explanations rather than source text."""

    raw_text = str(text or "").strip()
    if not raw_text:
        return False
    normalized = normalize_for_search(raw_text)
    has_summary_marker = any(marker in raw_text for marker in SUMMARY_ONLY_MARKERS) or "summary" in normalized
    if not has_summary_marker:
        return False
    if any(marker in raw_text for marker in ORIGINAL_SOURCE_MARKERS):
        return False
    nonempty_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    content_lines = [
        line
        for line in nonempty_lines
        if not SUMMARY_ONLY_LABEL_PATTERN.match(line)
        and not line.startswith("العنوان:")
        and not line.lower().startswith("title:")
    ]
    return not content_lines or len(raw_text) < 1500


def detect_query_intents(question: str) -> set[str]:
    """Return legal-question intents that should influence retrieval ranking."""

    normalized = normalize_for_search(question)
    intents: set[str] = set()
    for intent, terms in QUERY_INTENT_TERMS.items():
        if any(normalize_for_search(term) in normalized for term in terms):
            intents.add(intent)
    if re.search(r"\b(?:كم|كام|شلون|كيف).{0,30}(?:سعر|مبلغ|كلفة|تكلفة|دينار|دولار)\b", normalized):
        intents.add("amount")
    if re.search(r"\b(?:شنو|ما|ماهو|ما هو|اي|أي).{0,35}كتاب\b", normalized):
        intents.add("source_book")
    return intents


def expand_question_for_retrieval(question: str) -> str:
    """Add legal-domain synonyms so short or dialectal questions retrieve better."""

    parts = [question, normalize_for_search(question)]
    for intent in sorted(detect_query_intents(question)):
        parts.append(QUERY_INTENT_EXPANSIONS[intent])
    signals = extract_strong_signals(question)
    if signals:
        parts.append(" ".join(signals))
    return "\n".join(dict.fromkeys(part for part in parts if str(part).strip()))


def tokenize_for_search(text: str) -> set[str]:
    """Return meaningful normalized Arabic and numeric search tokens."""

    return set(tokenize_arabic_search(text))


def tokenize_bm25(text: str) -> list[str]:
    """Return normalized tokens for BM25 scoring."""

    return tokenize_arabic_search(text)


def extract_strong_signals(question: str) -> list[str]:
    """Extract high-value legal identifiers from the user question."""

    normalized = normalize_for_search(question)
    signals: list[str] = []
    signals.extend(DATE_PATTERN.findall(normalized))
    signals.extend(BOOK_NUMBER_PATTERN.findall(normalized))
    signals.extend(YEAR_PATTERN.findall(normalized))
    signals.extend(NUMBER_PATTERN.findall(normalized))
    for pattern in STRONG_ARABIC_PHRASE_PATTERNS:
        signals.extend(match.group(0).strip() for match in pattern.finditer(normalized))

    tokens = tokenize_arabic_search(normalized)
    for index, token in enumerate(tokens):
        if token in {"قرار", "كتاب", "رقم", "وزاره", "وزارة", "شركة", "منتوج"}:
            window = " ".join(tokens[index : index + 4])
            if window:
                signals.append(window)

    return list(dict.fromkeys(signal.strip() for signal in signals if signal.strip()))


def strong_signal_score(question: str, candidate_text: str) -> float:
    """Score exact identifiers more heavily than ordinary keyword overlap."""

    signals = extract_strong_signals(expand_question_for_retrieval(question))
    if not signals:
        return 0.0

    candidate = normalize_for_search(candidate_text)
    matched = 0.0
    total = 0.0
    for signal in signals:
        signal_text = normalize_for_search(signal)
        weight = 3.0 if any(char.isdigit() for char in signal_text) else 2.0
        total += weight
        signal_tokens = tokenize_for_search(signal_text)
        if signal_text and signal_text in candidate:
            matched += weight
        elif signal_tokens and signal_tokens <= tokenize_for_search(candidate):
            matched += weight * 0.8
    return matched / total if total else 0.0


def query_intent_score(question: str, candidate_text: str, metadata: dict | None = None) -> float:
    """Score whether a candidate contains the fields implied by the question."""

    intents = detect_query_intents(question)
    if not intents:
        return 0.0

    metadata = metadata or {}
    haystack = normalize_for_search(
        "\n".join(
            [
                candidate_text,
                metadata_search_text(metadata),
                " ".join(str(value) for value in metadata.values() if isinstance(value, (str, int, float, bool))),
            ]
        )
    )
    matched = 0
    for intent in intents:
        expansion_tokens = tokenize_for_search(QUERY_INTENT_EXPANSIONS[intent])
        if expansion_tokens and expansion_tokens & tokenize_for_search(haystack):
            matched += 1
            continue
        if intent == "source_book" and re.search(r"كتاب.{0,80}المرقم.{0,50}المؤرخ", haystack):
            matched += 1
        elif intent == "amount" and re.search(r"\b[0-9][0-9.,/ ]*\s*(?:دينار|دولار)\b", haystack):
            matched += 1
        elif intent == "date" and re.search(r"\b[0-9]{1,2}\s*/\s*[0-9]{1,2}\s*/\s*[0-9]{4}\b", haystack):
            matched += 1
        elif intent == "decision_number" and str(metadata.get("decision_number") or "").strip():
            matched += 1
    return matched / len(intents) if intents else 0.0


def bm25_scores(question: str, documents: list[str]) -> list[float]:
    """Score candidate documents with BM25 without requiring extra packages."""

    query_tokens = tokenize_bm25(question)
    tokenized_documents = [tokenize_bm25(document) for document in documents]
    if not query_tokens or not tokenized_documents:
        return [0.0 for _ in documents]

    average_length = sum(len(tokens) for tokens in tokenized_documents) / len(
        tokenized_documents
    )
    if average_length == 0:
        return [0.0 for _ in documents]

    document_frequency = {}
    for tokens in tokenized_documents:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    k1 = 1.5
    b = 0.75
    total_documents = len(tokenized_documents)
    scores = []

    for tokens in tokenized_documents:
        term_frequency = {}
        for token in tokens:
            term_frequency[token] = term_frequency.get(token, 0) + 1

        score = 0.0
        document_length = len(tokens)
        for token in query_tokens:
            frequency = term_frequency.get(token, 0)
            if not frequency:
                continue
            df = document_frequency.get(token, 0)
            idf = math.log(1 + (total_documents - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1 - b + b * document_length / average_length
            )
            score += idf * (frequency * (k1 + 1)) / denominator
        scores.append(score)

    max_score = max(scores) if scores else 0.0
    if max_score <= 0:
        return [0.0 for _ in documents]
    return [score / max_score for score in scores]


def metadata_search_text(metadata: dict) -> str:
    """Return searchable legal metadata without making filenames decisive."""

    values = []
    for key, value in metadata.items():
        if "filename" in str(key).lower() or key in {"source_file", "source"}:
            continue
        if isinstance(value, (str, int, float, bool)) and str(value).strip():
            values.append(str(value))
    return " ".join(values)


def candidate_search_text(document: str, metadata: dict) -> str:
    """Combine retrieved content with structured metadata for reranking."""

    metadata_text = metadata_search_text(metadata)
    return f"{document}\n{metadata_text}".strip()


def needs_multiple_documents(question: str) -> bool:
    """Return whether the query asks for a set of relevant documents."""

    normalized = normalize_for_search(question)
    patterns = (
        r"\b(?:ما|ماهي|ما هي|اذكر|اعرض|عدد)\s+ال?قرارات\b",
        r"\b(?:كل|جميع|كافة)\s+ال?قرارات\b",
        r"\bال?قرارات\s+التي\b",
        r"\bخلال\s+(?:سنة\s+)?(?:19|20)\d{2}\b",
        r"\b(?:قارن|مقارنة|بين)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def document_dedupe_key(metadata: dict, document: str = "") -> str:
    """Return a stable key for document-level de-duplication."""

    for key in ("document_id", "source_file", "document_title", "title"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return normalize_for_search(value)
    return normalize_for_search(document[:160])


def load_chunk_records(file_path: Path = CHUNKS_FILE) -> list[dict]:
    """Load locally saved chunks for metadata and lexical retrieval layers."""

    if not file_path.exists():
        return []
    records: list[dict] = []
    with file_path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record = repair_json_text(record)
            if not str(record.get("text") or "").strip():
                legacy_text = legacy_record_text(record)
                if legacy_text:
                    record["text"] = legacy_text
            if record.get("text") and not is_summary_only_chunk_text(str(record.get("text") or "")):
                records.append(record)
    return records


def legacy_record_text(record: dict) -> str:
    """Recover answerable text from older chunk files whose text field is empty."""

    document = record.get("document_document")
    if isinstance(document, dict):
        for key in ("text", "content", "body", "long_text"):
            value = str(document.get(key) or "").strip()
            if value:
                return value
        raw_payload = document.get("raw_payload")
        if isinstance(raw_payload, dict):
            for key in ("content", "text", "body", "long_text"):
                value = str(raw_payload.get(key) or "").strip()
                if value:
                    return value
    return ""


def _record_metadata(record: dict) -> dict:
    return {
        key: value
        for key, value in record.items()
        if key not in {"text", "embedding_text", "metadata"}
        and isinstance(value, (str, int, float, bool))
    }


def _candidate_results(scored_records: list[tuple[float, dict]], layer: str) -> dict:
    documents = []
    metadatas = []
    distances = []
    for score, record in scored_records:
        metadata = _record_metadata(record)
        metadata["chunk_id"] = str(record.get("chunk_id") or record.get("id") or "")
        metadata["retrieval_layer"] = layer
        documents.append(str(record.get("text") or ""))
        metadatas.append(metadata)
        distances.append(max(0.0, 1.0 - min(score, 1.0)))
    return {"documents": [documents], "metadatas": [metadatas], "distances": [distances]}


def metadata_filter_candidates(question: str, records: list[dict], limit: int = METADATA_CANDIDATE_COUNT) -> dict:
    """Layer 1: select chunks whose structured metadata matches strong signals."""

    expanded_question = expand_question_for_retrieval(question)
    signals = extract_strong_signals(expanded_question)
    if not signals:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    scored: list[tuple[float, dict]] = []
    for record in records:
        metadata = _record_metadata(record)
        haystack = metadata_search_text(metadata)
        score = (
            0.75 * strong_signal_score(" ".join(signals), haystack)
            + 0.25 * query_intent_score(question, haystack, metadata)
        )
        if score > 0:
            scored.append((score, record))
    scored.sort(key=lambda item: item[0], reverse=True)
    return _candidate_results(scored[:limit], "metadata")


def lexical_search_candidates(question: str, records: list[dict], limit: int = LEXICAL_CANDIDATE_COUNT) -> dict:
    """Layer 2: keyword/BM25 retrieval over saved chunk text and metadata."""

    if not records:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    expanded_question = expand_question_for_retrieval(question)
    texts = [
        candidate_search_text(str(record.get("text") or ""), _record_metadata(record))
        for record in records
    ]
    bm25_values = bm25_scores(expanded_question, texts)
    scored = []
    for index, record in enumerate(records):
        metadata = _record_metadata(record)
        lexical_score = lexical_relevance(expanded_question, texts[index])
        signal_score = strong_signal_score(question, texts[index])
        intent_score = query_intent_score(question, texts[index], metadata)
        score = (
            (0.45 * bm25_values[index])
            + (0.25 * lexical_score)
            + (0.20 * signal_score)
            + (0.10 * intent_score)
        )
        if score > 0:
            scored.append((score, record))
    scored.sort(key=lambda item: item[0], reverse=True)
    return _candidate_results(scored[:limit], "lexical")


def merge_candidate_results(*result_sets: dict, question: str = "") -> dict:
    """Merge retrieval layers while preserving the best score per chunk."""

    by_key: dict[str, dict] = {}
    for results in result_sets:
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for index, (document, metadata) in enumerate(zip(documents, metadatas)):
            metadata = metadata if isinstance(metadata, dict) else {}
            chunk_id = str(metadata.get("chunk_id") or metadata.get("id") or "")
            key = chunk_id or f"{metadata.get('source_file', '')}|{metadata.get('chunk_index', index)}|{document[:80]}"
            distance = distances[index] if index < len(distances) else 1.0
            layer = str(metadata.get("retrieval_layer") or "semantic")
            existing = by_key.get(key)
            if existing is None:
                merged_metadata = dict(metadata)
                merged_metadata["retrieval_layers"] = layer
                by_key[key] = {
                    "document": document,
                    "metadata": merged_metadata,
                    "distance": distance,
                }
                continue
            existing_document = str(existing.get("document") or "").strip()
            candidate_document = str(document or "").strip()
            if candidate_document and (
                not existing_document or float(distance) < float(existing["distance"])
            ):
                existing["document"] = document
                existing["distance"] = distance
            layers = set(str(existing["metadata"].get("retrieval_layers", "")).split("|"))
            layers.add(layer)
            existing["metadata"]["retrieval_layers"] = "|".join(sorted(value for value in layers if value))

    return {
        "_question": question,
        "documents": [[item["document"] for item in by_key.values()]],
        "metadatas": [[item["metadata"] for item in by_key.values()]],
        "distances": [[item["distance"] for item in by_key.values()]],
    }


def lexical_relevance(question: str, document: str) -> float:
    """Score exact legal terms and numbers that vector search can underweight."""

    question_tokens = tokenize_for_search(question)
    if not question_tokens:
        return 0.0

    document_tokens = tokenize_for_search(document)
    matched_weight = 0.0
    total_weight = 0.0

    for token in question_tokens:
        weight = 3.0 if token.isdigit() else 1.0
        total_weight += weight
        if token in document_tokens:
            matched_weight += weight

    score = matched_weight / total_weight
    normalized_question = normalize_for_search(question)
    normalized_document = normalize_for_search(document)
    if len(normalized_question) >= 8 and normalized_question in normalized_document:
        score += 0.2

    return min(score, 1.0)


def rerank_results(results: dict, result_count: int = RESULT_COUNT) -> dict:
    """Combine semantic and lexical relevance and remove near duplicates."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    question = results.get("_question", "")
    expanded_question = expand_question_for_retrieval(question)
    normalized_question = normalize_for_search(question)
    candidate_texts = [
        candidate_search_text(str(document or ""), metadata if isinstance(metadata, dict) else {})
        for document, metadata in zip(documents, metadatas)
    ]
    bm25_score_values = bm25_scores(expanded_question, candidate_texts)

    ranked = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas)):
        if is_summary_only_chunk_text(str(document or "")):
            continue
        metadata = metadata if isinstance(metadata, dict) else {}
        candidate_text = candidate_search_text(str(document or ""), metadata)
        distance = distances[index] if index < len(distances) else float("inf")
        semantic_score = 1.0 / (1.0 + max(float(distance), 0.0))
        lexical_score = lexical_relevance(expanded_question, candidate_text)
        bm25_score = (
            bm25_score_values[index]
            if index < len(bm25_score_values)
            else 0.0
        )
        signal_score = strong_signal_score(question, candidate_text)
        intent_score = query_intent_score(question, candidate_text, metadata)
        layers = set(str(metadata.get("retrieval_layers") or metadata.get("retrieval_layer") or "").split("|"))
        layer_bonus = 0.0
        if "metadata" in layers:
            layer_bonus += 0.08
        if "lexical" in layers:
            layer_bonus += 0.05
        if "semantic" in layers:
            layer_bonus += 0.03
        section = normalize_for_search(
            metadata.get("section")
            or metadata.get("section_title")
            or metadata.get("article_reference")
            or ""
        )
        structure_penalty = 0.0
        if section in {"header", "signature"} and re.search(
            r"\b(?:الموافقه|استثناء|عقد|مبلغ|مده|رقم|تعليمات|الماده)\b",
            normalized_question,
        ):
            structure_penalty = 0.12
        ranked.append(
            {
                "document": document,
                "metadata": metadata,
                "distance": distance,
                "score": (
                    (0.25 * semantic_score)
                    + (0.28 * bm25_score)
                    + (0.19 * lexical_score)
                    + (0.20 * signal_score)
                    + (0.08 * intent_score)
                    + layer_bonus
                    - structure_penalty
                ),
                "bm25_score": bm25_score,
                "signal_score": signal_score,
                "intent_score": intent_score,
                "tokens": tokenize_for_search(candidate_text),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    if needs_multiple_documents(question):
        by_document: dict[str, dict] = {}
        for candidate in ranked:
            key = document_dedupe_key(candidate["metadata"], str(candidate["document"] or ""))
            existing = by_document.get(key)
            if existing is None or float(candidate["score"]) > float(existing["score"]):
                by_document[key] = candidate
        selected = sorted(by_document.values(), key=lambda item: item["score"], reverse=True)[:result_count]
        return {
            "documents": [[item["document"] for item in selected]],
            "metadatas": [[item["metadata"] for item in selected]],
            "distances": [[item["distance"] for item in selected]],
            "relevance_scores": [[item["score"] for item in selected]],
            "bm25_scores": [[item["bm25_score"] for item in selected]],
            "signal_scores": [[item["signal_score"] for item in selected]],
            "intent_scores": [[item["intent_score"] for item in selected]],
        }

    selected = []
    for candidate in ranked:
        is_near_duplicate = False
        for existing in selected:
            union = candidate["tokens"] | existing["tokens"]
            overlap = (
                len(candidate["tokens"] & existing["tokens"]) / len(union)
                if union
                else 0.0
            )
            if overlap >= 0.85:
                is_near_duplicate = True
                break

        if not is_near_duplicate:
            selected.append(candidate)
        if len(selected) == result_count:
            break

    if len(selected) < result_count:
        selected_ids = {id(item) for item in selected}
        selected.extend(
            item
            for item in ranked
            if id(item) not in selected_ids
        )
        selected = selected[:result_count]

    return {
        "documents": [[item["document"] for item in selected]],
        "metadatas": [[item["metadata"] for item in selected]],
        "distances": [[item["distance"] for item in selected]],
        "relevance_scores": [[item["score"] for item in selected]],
        "bm25_scores": [[item["bm25_score"] for item in selected]],
        "signal_scores": [[item["signal_score"] for item in selected]],
        "intent_scores": [[item["intent_score"] for item in selected]],
    }


def semantic_search_candidates(collection, question: str, question_embedding: list[float], limit: int) -> dict:
    """Layer 3: retrieve semantic candidates from the existing Chroma index."""

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(limit, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    for metadata in results.get("metadatas", [[]])[0]:
        if isinstance(metadata, dict):
            metadata["retrieval_layer"] = "semantic"
    results["_question"] = question
    return results


def search(question: str) -> dict:
    """Retrieve broad semantic candidates, then rerank exact legal matches."""

    try:
        from .runtime_settings import runtime_settings
    except ImportError:
        from runtime_settings import runtime_settings
    current = runtime_settings()
    active_client = ollama.Client(
        host=current["model"]["ollama_base_url"],
        timeout=current["model"]["request_timeout"],
    )
    normalized_question = normalize_for_search(question)
    expanded_question = expand_question_for_retrieval(question)
    embedding_query = "\n".join(
        dict.fromkeys(value for value in (question, normalized_question, expanded_question) if value)
    )
    embedding_response = active_client.embed(
        model=current["model"]["embedding_model"],
        input=embedding_query,
        keep_alive=EMBEDDING_QUERY_KEEP_ALIVE,
    )
    question_embedding = embedding_response["embeddings"][0]

    client = chromadb.PersistentClient(path=str(CHROMA_FOLDER))
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )

    if collection.count() == 0:
        raise ValueError("The legal document collection is empty.")

    chunk_records = load_chunk_records()
    metadata_results = metadata_filter_candidates(question, chunk_records)
    lexical_results = lexical_search_candidates(question, chunk_records)
    semantic_results = semantic_search_candidates(
        collection,
        question,
        question_embedding,
        CANDIDATE_COUNT,
    )
    candidate_results = merge_candidate_results(
        metadata_results,
        lexical_results,
        semantic_results,
        question=question,
    )
    result_count = (
        max(int(current["retrieval"]["result_count"]), AGGREGATE_RESULT_COUNT)
        if needs_multiple_documents(question)
        else int(current["retrieval"]["result_count"])
    )
    reranked_results = rerank_results(candidate_results, result_count=result_count)
    log_retrieval_results(question, reranked_results)
    return reranked_results


def print_results(results: dict) -> None:
    """Print ranked retrieval results with source metadata."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        print("No matching chunks were found.")
        return

    print()
    print("Top retrieval results")
    print("=" * 70)

    for rank, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        distance = distances[rank - 1] if rank <= len(distances) else None
        preview = document[:TEXT_PREVIEW_LENGTH]

        print(f"Rank: {rank}")
        print(f"Source file: {metadata.get('source_file', 'Unknown')}")
        print(f"Page number: {metadata.get('page_number', 'Unknown')}")
        if metadata.get("document_title"):
            print(f"Document title: {metadata['document_title']}")
        if metadata.get("legal_reference"):
            print(f"Legal reference: {metadata['legal_reference']}")
        if distance is not None:
            print(f"Distance: {distance:.6f}")
        print("Text preview:")
        print(preview)
        print("-" * 70)


def main() -> None:
    """Run one retrieval-quality test without calling the chat model."""

    try:
        question = get_question()
        results = search(question)
        print_results(results)
    except (EOFError, KeyboardInterrupt):
        print("\nSearch cancelled.")
        sys.exit(1)
    except ValueError as error:
        print(f"Search failed: {error}")
        sys.exit(1)
    except NotFoundError:
        print(
            f"Search failed: collection '{COLLECTION_NAME}' was not found. "
            "Run python app/build_index.py first."
        )
        sys.exit(1)
    except ConnectionError:
        print("Search failed: could not connect to Ollama.")
        print("Make sure the Ollama service is running.")
        sys.exit(1)
    except httpx.TimeoutException:
        print("Search failed: the Ollama embedding request timed out.")
        sys.exit(1)
    except ollama.ResponseError as error:
        print(f"Search failed: Ollama request error: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"Search failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
