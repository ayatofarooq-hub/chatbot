"""HTTP API for testing the legal chatbot with clients such as Postman."""

from pathlib import Path

import httpx
import ollama
from chromadb.errors import NotFoundError
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

try:
    from .build_index import COLLECTION_NAME
    from .citation_registry import (
        citations_for_metadatas,
        filter_results_to_registered,
        load_registry,
        registry_warnings_for_metadatas,
    )
    from .document_store import (
        delete_document,
        insert_document,
        list_documents,
        update_document,
    )
    from .rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from .search_index import search
except ImportError:
    # Support direct execution with: python app/api.py
    from build_index import COLLECTION_NAME
    from citation_registry import (
        citations_for_metadatas,
        filter_results_to_registered,
        load_registry,
        registry_warnings_for_metadatas,
    )
    from document_store import (
        delete_document,
        insert_document,
        list_documents,
        update_document,
    )
    from rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from search_index import search


FRONTEND_FOLDER = Path(__file__).resolve().parent.parent / "frontend"


def extract_citations(answer: str) -> list[dict]:
    """Return unique citations from an answer in their original order."""

    citations = []
    seen = set()
    for source_file, page_number in CITATION_PATTERN.findall(answer):
        citation = (source_file.strip(), page_number)
        if citation in seen:
            continue
        seen.add(citation)
        citations.append(
            {
                "source_file": citation[0],
                "page_number": citation[1],
            }
        )
    return citations


def extract_snippets(results: dict) -> list[dict]:
    """Convert Chroma results into JSON-serializable evidence snippets."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    relevance_scores = results.get("relevance_scores", [[]])[0]
    bm25_scores = results.get("bm25_scores", [[]])[0]
    snippets = []

    for index, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        snippets.append(
            {
                "rank": index,
                "source_file": metadata.get("source_file"),
                "page_number": metadata.get("page_number"),
                "document_title": metadata.get("document_title"),
                "document_type": metadata.get("document_type"),
                "legal_reference": metadata.get("legal_reference"),
                "article_reference": metadata.get("article_reference"),
                "section_title": metadata.get("section_title"),
                "source_type": metadata.get("source_type"),
                "distance": (
                    distances[index - 1]
                    if index <= len(distances)
                    else None
                ),
                "relevance_score": (
                    relevance_scores[index - 1]
                    if index <= len(relevance_scores)
                    else None
                ),
                "bm25_score": (
                    bm25_scores[index - 1]
                    if index <= len(bm25_scores)
                    else None
                ),
                "text": document,
            }
        )

    return snippets


def result_metadatas(results: dict) -> list[dict]:
    """Return the top-level metadata list from a Chroma query response."""

    return results.get("metadatas", [[]])[0]


def extract_structured_citations(
    results: dict,
    registry: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """Return registry-backed citations and any citation integrity warnings."""

    metadatas = result_metadatas(results)
    registry = registry or load_registry()
    citations = citations_for_metadatas(metadatas, registry=registry)
    warnings = registry_warnings_for_metadatas(metadatas, registry=registry)
    return citations, warnings


def answer_question(question: str, include_snippets: bool = True) -> dict:
    """Run the shared chatbot flow and return an API response payload."""

    quick_response = get_quick_response(question)
    if quick_response:
        return {
            "question": question,
            "answer": quick_response,
            "warnings": [],
            "citations": [],
            "snippets": [],
        }

    results = search(question)
    registry = load_registry()
    validated_results, citation_warnings = filter_results_to_registered(
        results,
        registry=registry,
    )
    structured_citations, _ = extract_structured_citations(
        validated_results,
        registry=registry,
    )
    answer_result = generate_answer(question, validated_results)
    return {
        "question": question,
        "answer": answer_result.content,
        "warnings": answer_result.warnings + citation_warnings,
        "citations": structured_citations,
        "snippets": extract_snippets(validated_results) if include_snippets else [],
    }


async def health(_: Request) -> JSONResponse:
    """Return a lightweight process health response."""

    return JSONResponse({"status": "ok"})


async def frontend(_: Request) -> FileResponse:
    """Serve the standalone browser frontend."""

    return FileResponse(FRONTEND_FOLDER / "index.html")


async def favicon(_: Request) -> Response:
    """Acknowledge the browser's default favicon request."""

    return Response(status_code=204)


async def ask(request: Request) -> JSONResponse:
    """Accept a legal question and return a grounded chatbot answer."""

    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(
            {"detail": "Request body must be valid JSON."},
            status_code=400,
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            {"detail": "Request body must be a JSON object."},
            status_code=400,
        )

    question = payload.get("question")
    if not isinstance(question, str) or not question.strip():
        return JSONResponse(
            {"detail": "Field 'question' must be a non-empty string."},
            status_code=422,
        )

    include_snippets = payload.get("include_snippets", True)
    if not isinstance(include_snippets, bool):
        return JSONResponse(
            {"detail": "Field 'include_snippets' must be a boolean."},
            status_code=422,
        )

    try:
        response = await run_in_threadpool(
            answer_question,
            question.strip(),
            include_snippets,
        )
        return JSONResponse(response)
    except NotFoundError:
        return JSONResponse(
            {
                "detail": (
                    f"Collection '{COLLECTION_NAME}' was not found. "
                    "Run python app/build_index.py first."
                )
            },
            status_code=503,
        )
    except (ConnectionError, httpx.ConnectError):
        return JSONResponse(
            {"detail": "Could not connect to Ollama. Make sure it is running."},
            status_code=503,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            {"detail": "The Ollama request timed out."},
            status_code=504,
        )
    except ollama.ResponseError as error:
        return JSONResponse(
            {"detail": f"Ollama request failed: {error}"},
            status_code=502,
        )
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)


async def documents(_: Request) -> JSONResponse:
    """List source documents currently managed by the chatbot."""

    return JSONResponse({"documents": await run_in_threadpool(list_documents)})


async def create_document(request: Request) -> JSONResponse:
    """Insert a text document and index it."""

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        result = await run_in_threadpool(
            insert_document,
            payload.get("filename"),
            payload.get("content"),
        )
        return JSONResponse(result, status_code=201)
    except FileExistsError:
        return JSONResponse(
            {"detail": "A document with this filename already exists."},
            status_code=409,
        )
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except NotFoundError:
        return JSONResponse(
            {"detail": f"Collection '{COLLECTION_NAME}' was not found."},
            status_code=503,
        )
    except (ConnectionError, httpx.HTTPError):
        return JSONResponse(
            {"detail": "Could not connect to Ollama."},
            status_code=503,
        )


async def replace_document(request: Request) -> JSONResponse:
    """Replace a text document and its indexed chunks."""

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        result = await run_in_threadpool(
            update_document,
            request.path_params["filename"],
            payload.get("content"),
        )
        return JSONResponse(result)
    except FileNotFoundError:
        return JSONResponse({"detail": "Document not found."}, status_code=404)
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except NotFoundError:
        return JSONResponse(
            {"detail": f"Collection '{COLLECTION_NAME}' was not found."},
            status_code=503,
        )
    except (ConnectionError, httpx.HTTPError):
        return JSONResponse(
            {"detail": "Could not connect to Ollama."},
            status_code=503,
        )


async def remove_document(request: Request) -> JSONResponse:
    """Delete a text document and its indexed chunks."""

    try:
        result = await run_in_threadpool(
            delete_document,
            request.path_params["filename"],
        )
        return JSONResponse(result)
    except FileNotFoundError:
        return JSONResponse({"detail": "Document not found."}, status_code=404)
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except NotFoundError:
        return JSONResponse(
            {"detail": f"Collection '{COLLECTION_NAME}' was not found."},
            status_code=503,
        )


app = Starlette(
    debug=False,
    routes=[
        Route("/", frontend, methods=["GET"]),
        Route("/favicon.ico", favicon, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/ask", ask, methods=["POST"]),
        Route("/documents", documents, methods=["GET"]),
        Route("/documents", create_document, methods=["POST"]),
        Route("/documents/{filename:str}", replace_document, methods=["PUT"]),
        Route("/documents/{filename:str}", remove_document, methods=["DELETE"]),
        Mount(
            "/assets",
            app=StaticFiles(directory=FRONTEND_FOLDER),
            name="frontend-assets",
        ),
    ],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
