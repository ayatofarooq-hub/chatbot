"""Diagnostic search for testing retrieval quality in the legal index."""

import argparse
import math
import re
import sys
import unicodedata

import chromadb
import httpx
import ollama
from chromadb.errors import NotFoundError

try:
    from .build_index import COLLECTION_NAME
    from .config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from .ollama_client import client as ollama_client
except ImportError:
    # Support direct execution with: python app/search_index.py
    from build_index import COLLECTION_NAME
    from config import (
        CHROMA_FOLDER,
        EMBEDDING_MODEL,
        EMBEDDING_QUERY_KEEP_ALIVE,
    )
    from ollama_client import client as ollama_client


RESULT_COUNT = 5
CANDIDATE_COUNT = 20
TEXT_PREVIEW_LENGTH = 500
ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
TOKEN_PATTERN = re.compile(r"[\u0600-\u06ff]+|[0-9\u0660-\u0669]+")
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
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
    "من",
    "هل",
    "هو",
    "هي",
    "و",
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

    text = unicodedata.normalize("NFKC", text).translate(ARABIC_INDIC_DIGITS)
    text = ARABIC_DIACRITICS_PATTERN.sub("", text)
    text = text.replace("ـ", "")
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", text).strip().lower()


def tokenize_for_search(text: str) -> set[str]:
    """Return meaningful normalized Arabic and numeric search tokens."""

    normalized = normalize_for_search(text)
    tokens = {
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOP_WORDS and (token.isdigit() or len(token) > 1)
    }
    # PyMuPDF can reverse digit sequences in right-to-left PDF text. Keep both
    # forms for ranking so a query for 13/2005 matches extracted 31/5002.
    reversed_numbers = {
        token[::-1]
        for token in tokens
        if token.isdigit() and len(token) > 1
    }
    return tokens | reversed_numbers


def tokenize_bm25(text: str) -> list[str]:
    """Return normalized tokens for BM25 scoring."""

    normalized = normalize_for_search(text)
    tokens = [
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOP_WORDS and (token.isdigit() or len(token) > 1)
    ]
    expanded = []
    for token in tokens:
        expanded.append(token)
        if token.isdigit() and len(token) > 1:
            expanded.append(token[::-1])
    return expanded


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
    bm25_score_values = bm25_scores(question, documents)

    ranked = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas)):
        distance = distances[index] if index < len(distances) else float("inf")
        semantic_score = 1.0 / (1.0 + max(float(distance), 0.0))
        lexical_score = lexical_relevance(question, document)
        bm25_score = (
            bm25_score_values[index]
            if index < len(bm25_score_values)
            else 0.0
        )
        ranked.append(
            {
                "document": document,
                "metadata": metadata,
                "distance": distance,
                "score": (
                    (0.55 * semantic_score)
                    + (0.30 * bm25_score)
                    + (0.15 * lexical_score)
                ),
                "bm25_score": bm25_score,
                "tokens": tokenize_for_search(document),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
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
    }


def search(question: str) -> dict:
    """Retrieve broad semantic candidates, then rerank exact legal matches."""

    embedding_response = ollama_client.embed(
        model=EMBEDDING_MODEL,
        input=question,
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

    candidate_results = collection.query(
        query_embeddings=[question_embedding],
        n_results=min(CANDIDATE_COUNT, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    candidate_results["_question"] = question
    return rerank_results(candidate_results)


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
