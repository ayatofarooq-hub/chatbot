"""HTTP API for testing the legal chatbot with clients such as Postman."""

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
import asyncio
import mimetypes
import sys
import re
from urllib.parse import quote

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
    from .legal_lookup import answer_exact_law
    from .config import PROJECT_ROOT
    from .json_storage import read_json, write_json
    from .rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from .search_index import search
    from .text_encoding import repair_json_text
    from .speech_to_text import inspect_audio, transcribe_audio
    from .local_tts import (
        LocalTtsUnavailable, SYNTHESIS_TIMEOUT_SECONDS,
        synthesize_arabic, voice_status,
    )
    from .uploaded_documents import (
        create_uploaded_document,
        delete_uploaded_document,
        list_uploaded_documents,
        uploaded_file_path,
    )
    from .settings_api import (
        backup_create, backup_restore, classification_delete,
        classification_put, classification_reassign, classifications_get,
        classifications_post, index_rebuild, index_status, login, logout,
        model_test, session, settings_export, settings_get, settings_import,
        settings_put, settings_reset, audit_log_get, user_delete,
        user_password_post, user_put, users_get, users_post,
    )
    from .human_review import create_review_entry, decide_review, list_reviews
    from legal_rag.grounded_answer import answer_from_results as legal_rag_answer_from_results
except ImportError:
    # Support direct execution with: python app/api.py
    app_dir = str(Path(__file__).resolve().parent)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    
    from build_index import COLLECTION_NAME
    from citation_registry import (
        citations_for_metadatas,
        filter_results_to_registered,
        load_registry,
        registry_warnings_for_metadatas,
    )
    from legal_lookup import answer_exact_law
    from config import PROJECT_ROOT
    from json_storage import read_json, write_json
    from rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from search_index import search
    from text_encoding import repair_json_text
    from speech_to_text import inspect_audio, transcribe_audio
    from local_tts import (
        LocalTtsUnavailable, SYNTHESIS_TIMEOUT_SECONDS,
        synthesize_arabic, voice_status,
    )
    from uploaded_documents import (
        create_uploaded_document,
        delete_uploaded_document,
        list_uploaded_documents,
        uploaded_file_path,
    )
    from settings_api import (
        backup_create, backup_restore, classification_delete,
        classification_put, classification_reassign, classifications_get,
        classifications_post, index_rebuild, index_status, login, logout,
        model_test, session, settings_export, settings_get, settings_import,
        settings_put, settings_reset, audit_log_get, user_delete,
        user_password_post, user_put, users_get, users_post,
    )
    from human_review import create_review_entry, decide_review, list_reviews
    from legal_rag.grounded_answer import answer_from_results as legal_rag_answer_from_results


FRONTEND_FOLDER = Path(__file__).resolve().parent.parent / "frontend"
CHAT_HISTORY_FILE = PROJECT_ROOT / "data" / "chat_history.json"

# Windows can inherit a registry mapping that labels JavaScript as text/plain.
# Browsers reject ES modules served with that MIME type, leaving a blank page.
mimetypes.add_type("text/javascript", ".js")


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
                "source_file": repair_json_text(metadata.get("source_file")),
                "page_number": metadata.get("page_number"),
                "document_title": repair_json_text(metadata.get("document_title")),
                "document_type": repair_json_text(metadata.get("document_type")),
                "legal_reference": repair_json_text(metadata.get("legal_reference")),
                "article_reference": repair_json_text(metadata.get("article_reference")),
                "section_title": repair_json_text(metadata.get("section_title")),
                "source_type": repair_json_text(metadata.get("source_type")),
                "chunk_id": str(metadata.get("chunk_id") or metadata.get("id") or ""),
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
                "text": repair_json_text(document),
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


def source_from_metadata(metadata: dict, relevance_score: float | None = None) -> dict:
    """Return document-level source attribution for one retrieved JSON document."""

    filename = repair_json_text(metadata.get("source_file") or metadata.get("filename") or "")
    return {
        "document_id": repair_json_text(metadata.get("document_id") or ""),
        "filename": filename,
        "document_type": repair_json_text(metadata.get("document_type") or ""),
        "year": repair_json_text(metadata.get("year") or metadata.get("law_year") or ""),
        "issue_date": repair_json_text(metadata.get("issue_date") or ""),
        "relevance_score": relevance_score,
    }


def source_document_key(source: dict) -> str:
    """Return a stable source key so API sources are de-duplicated by document."""

    return str(source.get("document_id") or source.get("filename") or "").strip()


def source_hint_values(source_hint: object) -> set[str]:
    """Normalize previous-answer source hints sent by the frontend."""

    values: set[str] = set()
    if isinstance(source_hint, dict):
        candidates = source_hint.get("sources") or source_hint.get("items") or []
    elif isinstance(source_hint, list):
        candidates = source_hint
    else:
        candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        for key in ("document_id", "filename", "document_name", "source_file"):
            value = repair_json_text(item.get(key) or "").strip()
            if value:
                values.add(value)
    return values


def filter_results_by_source_hint(results: dict, source_hint: object) -> dict:
    """Keep retrieval hits from the same previous Word/doc source when possible."""

    hints = source_hint_values(source_hint)
    if not hints:
        return results

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not documents or not metadatas:
        return results

    keep_indexes = []
    for index, metadata in enumerate(metadatas):
        if not isinstance(metadata, dict):
            continue
        metadata_values = {
            repair_json_text(metadata.get("document_id") or "").strip(),
            repair_json_text(metadata.get("source_file") or "").strip(),
            repair_json_text(metadata.get("filename") or "").strip(),
            repair_json_text(metadata.get("source_filename") or "").strip(),
        }
        metadata_values.discard("")
        if hints & metadata_values:
            keep_indexes.append(index)

    if not keep_indexes:
        return results

    filtered = {**results}
    for key in ("documents", "metadatas", "distances", "relevance_scores", "bm25_scores"):
        values = results.get(key, [[]])
        row = values[0] if values and isinstance(values[0], list) else []
        if row:
            filtered[key] = [[row[index] for index in keep_indexes if index < len(row)]]
    return filtered


def sources_from_grounded_answer(grounded: dict, results: dict) -> list[dict]:
    """Map grounded answer sources to required API source objects."""

    by_chunk_id = {
        str(metadata.get("chunk_id") or metadata.get("id") or ""): metadata
        for metadata in result_metadatas(results)
    }
    relevance_by_chunk_id = {
        str(metadata.get("chunk_id") or metadata.get("id") or ""): (
            results.get("relevance_scores", [[]])[0][index]
            if index < len(results.get("relevance_scores", [[]])[0])
            else None
        )
        for index, metadata in enumerate(result_metadatas(results))
    }
    sources = []
    seen = set()
    for source in grounded.get("sources", []):
        chunk_id = str(source.get("chunk_id") or "")
        if not chunk_id:
            continue
        metadata = by_chunk_id.get(chunk_id, {})
        if metadata:
            item = source_from_metadata(metadata, relevance_by_chunk_id.get(chunk_id))
        else:
            item = {
                "document_id": repair_json_text(source.get("document_id") or ""),
                "filename": repair_json_text(source.get("document") or ""),
                "document_type": "",
                "year": "",
                "issue_date": "",
                "relevance_score": relevance_by_chunk_id.get(chunk_id),
            }
        key = source_document_key(item)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        sources.append(item)
    return sources


def full_text_sources_from_grounded_answer(grounded: dict, results: dict) -> list[dict]:
    """Map grounded full-text source records to API source objects."""

    by_chunk_id = {
        str(metadata.get("chunk_id") or metadata.get("id") or ""): metadata
        for metadata in result_metadatas(results)
    }
    sources = []
    seen = set()
    for source in grounded.get("full_text_sources", []):
        chunk_id = str(source.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        metadata = by_chunk_id.get(chunk_id, {})
        if metadata:
            item = source_from_metadata(metadata)
        else:
            item = {
                "document_name": repair_json_text(source.get("document") or ""),
                "document_type": "",
                "section": repair_json_text(source.get("section") or ""),
                "item_number": repair_json_text(source.get("item") or ""),
                "chunk_id": chunk_id,
            }
        item["full_text"] = repair_json_text(source.get("full_text") or "")
        item["full_text_length"] = len(item["full_text"])
        item["original_long_text"] = repair_json_text(source.get("original_long_text") or item["full_text"])
        item["original_long_text_length"] = len(item["original_long_text"])
        item["relevant_text"] = repair_json_text(source.get("relevant_text") or "")
        item["paragraph_indexes"] = list(source.get("paragraph_indexes") or [])
        item["document_id"] = repair_json_text(source.get("document_id") or "")
        item["filename"] = repair_json_text(source.get("filename") or source.get("document") or "")
        sources.append(item)
    return sources


def should_use_exact_law_lookup(question: str) -> bool:
    """Use the legacy exact-law shortcut only for explicit law lookups."""

    normalized = question.strip()
    law_terms = (
        "\u0642\u0627\u0646\u0648\u0646",
        "\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
        "\u0646\u0638\u0627\u0645",
    )
    factual_terms = (
        "\u0645\u0627 \u0647\u0648",
        "\u0645\u0627\u0647\u064a",
        "\u0645\u0627 \u0647\u064a",
        "\u0643\u0645",
        "\u0645\u0628\u0644\u063a",
        "\u0645\u062f\u0629",
        "\u0637\u0648\u0644",
        "\u0631\u0642\u0645 \u0627\u0644\u0637\u0644\u0628\u064a\u0629",
        "\u0627\u0644\u062c\u0647\u0629",
    )
    if not any(term in normalized for term in law_terms):
        return False
    if any(term in normalized for term in factual_terms):
        return False
    number = "\u0631\u0642\u0645"
    year = "\u0644\u0633\u0646\u0629"
    return bool(re.search(fr"{number}\s*\(?[0-9\u0660-\u0669]+\)?|{year}\s*\(?[0-9\u0660-\u0669]{{4}}\)?", normalized))


def answer_question(
    question: str,
    include_snippets: bool = True,
    source_hint: object | None = None,
) -> dict:
    """Run the shared chatbot flow and return an API response payload."""

    quick_response = get_quick_response(question)
    if quick_response:
        return {
            "question": question,
            "answer": quick_response,
            "sources": [],
            "full_text": "",
            "full_text_sources": [],
            "warnings": [],
            "citations": [],
            "snippets": [],
        }

    exact_answer = answer_exact_law(question) if should_use_exact_law_lookup(question) else None
    if exact_answer:
        return {
            "question": question,
            "answer": exact_answer["answer"],
            "sources": [
                {
                    "document_name": repair_json_text(
                        citation.get("source_file")
                        or citation.get("law_name")
                        or citation.get("legal_reference")
                        or ""
                    ),
                    "document_type": repair_json_text(citation.get("document_type") or ""),
                    "section": repair_json_text(
                        citation.get("article")
                        or citation.get("article_number")
                        or citation.get("legal_reference")
                        or ""
                    ),
                    "item_number": repair_json_text(
                        citation.get("article_number") or citation.get("article") or ""
                    ),
                    "chunk_id": str(citation.get("chunk_id") or ""),
                }
                for citation in exact_answer["citations"]
            ],
            "full_text": "",
            "full_text_sources": [],
            "warnings": [],
            "citations": exact_answer["citations"],
            "snippets": exact_answer["snippets"] if include_snippets else [],
        }

    results = filter_results_by_source_hint(search(question), source_hint)
    registry = load_registry()
    validated_results, _ = filter_results_to_registered(
        results,
        registry=registry,
    )
    answer_results = validated_results
    if not validated_results.get("documents", [[]])[0] and results.get("documents", [[]])[0]:
        answer_results = results
    structured_citations, _ = extract_structured_citations(
        validated_results,
        registry=registry,
    )
    grounded_answer = legal_rag_answer_from_results(question, answer_results)
    sources = sources_from_grounded_answer(grounded_answer, answer_results)
    full_text_sources = full_text_sources_from_grounded_answer(
        grounded_answer,
        answer_results,
    )
    return {
        "question": question,
        "answer": grounded_answer["answer"],
        "sources": sources,
        "full_text": grounded_answer.get("full_text", ""),
        "full_text_sources": full_text_sources,
        "confidence": grounded_answer.get("confidence", 0.0),
        "warnings": [],
        "citations": structured_citations,
        "snippets": extract_snippets(answer_results) if include_snippets else [],
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


def authenticated_admin(request: Request):
    from .auth import COOKIE_NAME, admin_for_token
    from .runtime_settings import runtime_settings

    if not runtime_settings()["authentication"]["login_enabled"]:
        return {"authentication_disabled": True}
    return admin_for_token(request.cookies.get(COOKIE_NAME))


async def uploads_get(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    return JSONResponse({"items": await run_in_threadpool(list_uploaded_documents)})


async def upload_settings_get(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    from .runtime_settings import runtime_settings

    settings = runtime_settings()["upload"]
    return JSONResponse(
        {
            "max_file_count": settings["max_file_count"],
            "max_file_size_mb": settings["max_file_size_mb"],
        }
    )


async def uploads_post(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        form = await request.form()
        uploaded = form.get("file")
        if uploaded is None or not hasattr(uploaded, "read"):
            return JSONResponse({"detail": "Field 'file' is required."}, status_code=422)
        from .runtime_settings import runtime_settings

        maximum = int(runtime_settings()["upload"]["max_file_size_mb"]) * 1024 * 1024
        content = await uploaded.read(maximum + 1)
        filename = str(getattr(uploaded, "filename", "") or "document")
        await uploaded.close()
        if len(content) > maximum:
            return JSONResponse(
                {"detail": f"File exceeds the {maximum // (1024 * 1024)} MB limit."},
                status_code=413,
            )
        item = await run_in_threadpool(create_uploaded_document, filename, content)
        return JSONResponse(item, status_code=201)
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except NotFoundError:
        return JSONResponse(
            {"detail": "Search index is not initialized. Rebuild the index first."},
            status_code=503,
        )
    except (ConnectionError, httpx.HTTPError, ollama.ResponseError) as error:
        return JSONResponse({"detail": f"Indexing failed: {error}"}, status_code=503)


async def upload_delete(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        await run_in_threadpool(
            delete_uploaded_document,
            request.path_params["upload_id"],
        )
        return JSONResponse({"removed_from_uploads": True, "retained_as_source": True})
    except LookupError as error:
        return JSONResponse({"detail": str(error)}, status_code=404)


async def upload_download(request: Request) -> Response:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        path, filename = await run_in_threadpool(
            uploaded_file_path,
            request.path_params["upload_id"],
        )
        return FileResponse(path, filename=filename)
    except LookupError as error:
        return JSONResponse({"detail": str(error)}, status_code=404)


MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
}


async def transcribe(request: Request) -> JSONResponse:
    """Accept a short recording and transcribe it locally as Arabic."""

    try:
        form = await request.form()
    except Exception:
        return JSONResponse(
            {"detail": "Request must contain multipart form data."},
            status_code=400,
        )

    audio = form.get("audio")
    if audio is None or not hasattr(audio, "read"):
        return JSONResponse(
            {"detail": "Field 'audio' must contain an audio file."},
            status_code=422,
        )

    content_type = (getattr(audio, "content_type", "") or "").split(";", 1)[0]
    if content_type not in ALLOWED_AUDIO_TYPES:
        await audio.close()
        return JSONResponse(
            {"detail": "Unsupported audio format."},
            status_code=415,
        )

    content = await audio.read(MAX_AUDIO_BYTES + 1)
    await audio.close()
    if not content:
        return JSONResponse({"detail": "The recording is empty."}, status_code=422)
    if len(content) > MAX_AUDIO_BYTES:
        return JSONResponse(
            {"detail": "The recording exceeds the 10 MB limit."},
            status_code=413,
        )

    suffix = Path(getattr(audio, "filename", "") or ".webm").suffix or ".webm"
    temporary_path = None
    try:
        with NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        diagnostics = await run_in_threadpool(inspect_audio, temporary_path)
        print(f"Speech audio diagnostics: {diagnostics}", flush=True)
        text = await run_in_threadpool(transcribe_audio, temporary_path)
        return JSONResponse({"text": text, "language": "ar"})
    except ValueError as error:
        level = diagnostics.get("rms", 0.0) if "diagnostics" in locals() else 0.0
        duration = (
            diagnostics.get("duration_seconds", 0.0)
            if "diagnostics" in locals()
            else 0.0
        )
        return JSONResponse(
            {
                "detail": (
                    f"{error} مدة التسجيل: {duration} ثانية، "
                    f"مستوى الإشارة: {level}."
                )
            },
            status_code=422,
        )
    except RuntimeError as error:
        return JSONResponse({"detail": str(error)}, status_code=503)
    except Exception:
        return JSONResponse(
            {"detail": "Audio transcription failed."},
            status_code=500,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


async def tts_status(_: Request) -> JSONResponse:
    """Report whether the offline Arabic voice is installed and ready."""

    return JSONResponse(voice_status())


async def text_to_speech(request: Request) -> Response:
    """Generate a short Arabic WAV clip entirely on the local machine."""

    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(
            {"detail": "Request body must be valid JSON."}, status_code=400
        )
    if not isinstance(payload, dict):
        return JSONResponse(
            {"detail": "Request body must be a JSON object."}, status_code=400
        )

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return JSONResponse(
            {"detail": "Field 'text' must be a non-empty string."},
            status_code=422,
        )
    language = payload.get("language", "ar")
    if not isinstance(language, str) or not language.lower().startswith("ar"):
        return JSONResponse(
            {"detail": "حقل 'language' يجب أن يحدد اللغة العربية."}, status_code=422
        )
    speed = payload.get("rate", payload.get("speed", 1.0))
    if isinstance(speed, bool) or not isinstance(speed, (int, float)):
        return JSONResponse(
            {"detail": "Field 'speed' must be a number."}, status_code=422
        )
    if not 0.75 <= float(speed) <= 1.25:
        return JSONResponse(
            {"detail": "سرعة النطق يجب أن تكون بين 0.75 و1.25."}, status_code=422
        )

    try:
        wav_content = await asyncio.wait_for(
            run_in_threadpool(synthesize_arabic, text, speed),
            timeout=SYNTHESIS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return JSONResponse(
            {"detail": "استغرق إنشاء الصوت المحلي وقتاً أطول من المسموح."},
            status_code=504,
        )
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)
    except LocalTtsUnavailable as error:
        return JSONResponse({"detail": str(error)}, status_code=503)
    except RuntimeError as error:
        return JSONResponse({"detail": str(error)}, status_code=500)
    return Response(
        content=wav_content,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


async def ask(request: Request) -> JSONResponse:
    """Accept a legal question and return a grounded chatbot answer."""

    try:
        from .auth import COOKIE_NAME, admin_for_token
        from .runtime_settings import runtime_settings
        auth_settings = runtime_settings()["authentication"]
        if (
            auth_settings["login_enabled"]
            and not admin_for_token(request.cookies.get(COOKIE_NAME))
        ):
            return JSONResponse(
                {"detail": "Authentication required."}, status_code=401
            )
    except ImportError:
        pass
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

    source_hint = payload.get("source_hint")
    if source_hint is not None and not isinstance(source_hint, (dict, list)):
        return JSONResponse(
            {"detail": "Field 'source_hint' must be an object or array when provided."},
            status_code=422,
        )

    try:
        response = await run_in_threadpool(
            answer_question,
            question.strip(),
            include_snippets,
            source_hint,
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
            {
                "detail": (
                    "انتهت مهلة انتظار نموذج Ollama. "
                    "النموذج المحلي بطيء أو لا يملك موارد كافية؛ "
                    "حاول مرة أخرى أو اختر نموذجاً أصغر من الإعدادات."
                )
            },
            status_code=504,
        )
    except ollama.ResponseError as error:
        return JSONResponse(
            {"detail": f"Ollama request failed: {error}"},
            status_code=502,
        )
    except ValueError as error:
        return JSONResponse({"detail": str(error)}, status_code=422)


def normalized_chat_history_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"conversations": [], "activeConversationId": None}
    conversations = payload.get("conversations", [])
    if not isinstance(conversations, list):
        conversations = []
    return {
        "conversations": conversations,
        "activeConversationId": payload.get("activeConversationId"),
        "updatedAt": payload.get("updatedAt") or datetime.now().isoformat(),
    }


async def chat_history_get(_: Request) -> JSONResponse:
    """Return browser-independent chat history persisted on the server."""

    return JSONResponse(
        normalized_chat_history_payload(
            await run_in_threadpool(read_json, CHAT_HISTORY_FILE, {})
        )
    )


async def chat_history_put(request: Request) -> JSONResponse:
    """Persist chat history so refreshes do not depend only on localStorage."""

    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(
            {"detail": "Request body must be valid JSON."},
            status_code=400,
        )

    normalized = normalized_chat_history_payload(payload)
    await run_in_threadpool(write_json, CHAT_HISTORY_FILE, normalized)
    return JSONResponse({"saved": True})


async def reviews_get(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    return JSONResponse({"items": list_reviews()})


async def reviews_post(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"detail": "Request body must be valid JSON."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Request body must be a JSON object."}, status_code=400)
    try:
        review = create_review_entry(
            review_id=str(payload.get("review_id") or "review_" + datetime.now().strftime("%Y%m%d%H%M%S")),
            upload_id=str(payload.get("upload_id") or ""),
            filename=str(payload.get("filename") or "document"),
            original_text=str(payload.get("original_text") or ""),
            extracted_metadata=dict(payload.get("extracted_metadata") or {}),
            generated_payload=dict(payload.get("generated_payload") or {}),
            validation_status=str(payload.get("validation_status") or "pending"),
            processing_log=list(payload.get("processing_log") or []),
        )
        return JSONResponse(review, status_code=201)
    except Exception as error:
        return JSONResponse({"detail": str(error)}, status_code=422)


async def reviews_decide(request: Request) -> JSONResponse:
    if not authenticated_admin(request):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"detail": "Request body must be valid JSON."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Request body must be a JSON object."}, status_code=400)
    review_id = str(payload.get("review_id") or "")
    decision = str(payload.get("decision") or "reject")
    if not review_id:
        return JSONResponse({"detail": "Field 'review_id' is required."}, status_code=422)
    try:
        return JSONResponse(
            decide_review(
                review_id,
                decision=decision,
                reviewer=str(payload.get("reviewer") or "admin"),
                reason=str(payload.get("reason") or ""),
                metadata=dict(payload.get("metadata") or {}),
            )
        )
    except LookupError as error:
        return JSONResponse({"detail": str(error)}, status_code=404)


async def export_chat(request: Request) -> Response:
    """Export a conversation as Markdown or plain text."""

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

    title = payload.get("title", "محادثة قانونية")
    messages = payload.get("messages", [])
    export_format = request.query_params.get("format", "md").lower()

    if export_format not in ("pdf", "txt"):
        return JSONResponse(
            {"detail": "Format must be 'pdf' or 'txt'."},
            status_code=422,
        )

    if not isinstance(messages, list):
        return JSONResponse(
            {"detail": "Field 'messages' must be an array."},
            status_code=422,
        )

    if not messages:
        return JSONResponse(
            {"detail": "Conversation has no messages."},
            status_code=422,
        )

    # Format the conversation
    lines = []
    lines.append(f"المحادثة: {title}")
    lines.append(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-" * 50)
    lines.append("")

    for message in messages:
        if not isinstance(message, dict):
            continue
        
        role = message.get("role", "unknown")
        content = message.get("content", "")
        time = message.get("time", "")
        
        # Format based on role
        if role == "user":
            lines.append(f"المستخدم: {time}")
            lines.append(content)
        elif role == "assistant":
            lines.append(f"المساعد: {time}")
            lines.append(content)
            
            # Add citations if present
            citations = message.get("citations", [])
            if citations:
                lines.append("")
                lines.append("المصادر:")
                for citation in citations:
                    if isinstance(citation, dict):
                        ref = citation.get("legal_reference", "")
                        source = citation.get("source_file", "")
                        page = citation.get("page_number", "")
                        if ref:
                            lines.append(f"  - {ref}")
                        elif source and page:
                            lines.append(f"  - {source}، الصفحة {page}")
            
            # Add warnings if present
            warnings = message.get("warnings", [])
            if warnings:
                lines.append("")
                lines.append("ملاحظات:")
                for warning in warnings:
                    lines.append(f"  - {warning}")
        
        lines.append("")
        lines.append("-" * 50)
        lines.append("")

    content = "\n".join(lines)

    # Return based on format
    if export_format == "pdf":
        import fitz

        message_html = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = "المستخدم" if message.get("role") == "user" else "المساعد"
            body = escape(str(message.get("content", ""))).replace("\n", "<br>")
            time = escape(str(message.get("time", "")))
            message_html.append(
                f'<section class="message"><h2>{escape(role)}'
                f'<small>{time}</small></h2><p>{body}</p></section>'
            )
        html = (
            '<html dir="rtl"><body>'
            f"<h1>{escape(str(title))}</h1>"
            f'<p class="date">{datetime.now():%Y-%m-%d %H:%M:%S}</p>'
            + "".join(message_html)
            + "</body></html>"
        )
        css = """
            @page { size: a4; margin: 54pt; }
            body { direction: rtl; font-family: sans-serif; color: #17211b; }
            h1 { color: #145a38; font-size: 24pt; margin-bottom: 4pt; }
            .date { color: #68736d; margin-bottom: 24pt; }
            .message { border-bottom: 1px solid #dfe5e1; padding: 10pt 0; }
            h2 { color: #145a38; font-size: 13pt; margin: 0 0 7pt; }
            h2 small { color: #78817c; font-size: 8pt; margin-right: 8pt; }
            p { font-size: 11pt; line-height: 1.7; margin: 0; }
        """
        story = fitz.Story(html=html, user_css=css)
        output = BytesIO()
        writer = fitz.DocumentWriter(output)

        def pdf_page(_rect_number, _filled):
            return (
                fitz.Rect(0, 0, 595, 842),
                fitz.Rect(54, 54, 541, 788),
                None,
            )

        story.write(writer, pdf_page)
        writer.close()
        content_bytes = output.getvalue()
        filename = f"{title.replace('/', '-').replace(' ', '_')}.pdf"
        media_type = "application/pdf"
    else:
        filename = f"{title.replace('/', '-').replace(' ', '_')}.txt"
        media_type = "text/plain; charset=utf-8"
        content_bytes = content.encode("utf-8")

    encoded_filename = quote(filename, safe="")
    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="conversation.{export_format}"; '
                f"filename*=UTF-8''{encoded_filename}"
            ),
        },
    )


app = Starlette(
    debug=False,
    routes=[
        Route("/", frontend, methods=["GET"]),
        Route("/favicon.ico", favicon, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/transcribe", transcribe, methods=["POST"]),
        Route("/api/tts/status", tts_status, methods=["GET"]),
        Route("/api/tts", text_to_speech, methods=["POST"]),
        Route("/ask", ask, methods=["POST"]),
        Route("/api/chat-history", chat_history_get, methods=["GET"]),
        Route("/api/chat-history", chat_history_put, methods=["POST", "PUT"]),
        Route("/api/export-chat", export_chat, methods=["POST"]),
        Route("/api/reviews", reviews_get, methods=["GET"]),
        Route("/api/reviews", reviews_post, methods=["POST"]),
        Route("/api/reviews/decide", reviews_decide, methods=["POST"]),
        Route("/api/uploads", uploads_get, methods=["GET"]),
        Route("/api/uploads/settings", upload_settings_get, methods=["GET"]),
        Route("/api/uploads", uploads_post, methods=["POST"]),
        Route("/api/uploads/{upload_id:str}", upload_delete, methods=["DELETE"]),
        Route("/api/uploads/{upload_id:str}/download", upload_download, methods=["GET"]),
        Route("/api/auth/login", login, methods=["POST"]),
        Route("/api/auth/logout", logout, methods=["POST"]),
        Route("/api/auth/session", session, methods=["GET"]),
        Route("/api/settings", settings_get, methods=["GET"]),
        Route("/api/settings", settings_put, methods=["PUT"]),
        Route("/api/settings/reset", settings_reset, methods=["POST"]),
        Route("/api/settings/classifications", classifications_get, methods=["GET"]),
        Route("/api/settings/classifications", classifications_post, methods=["POST"]),
        Route("/api/settings/classifications/{id:int}", classification_put, methods=["PUT"]),
        Route("/api/settings/classifications/{id:int}", classification_delete, methods=["DELETE"]),
        Route("/api/settings/classifications/{id:int}/reassign", classification_reassign, methods=["POST"]),
        Route("/api/settings/model/test", model_test, methods=["POST"]),
        Route("/api/settings/index/rebuild", index_rebuild, methods=["POST"]),
        Route("/api/settings/index/status", index_status, methods=["GET"]),
        Route("/api/settings/export", settings_export, methods=["GET"]),
        Route("/api/settings/import", settings_import, methods=["POST"]),
        Route("/api/settings/backup", backup_create, methods=["POST"]),
        Route("/api/settings/restore", backup_restore, methods=["POST"]),
        Route("/api/settings/users", users_get, methods=["GET"]),
        Route("/api/settings/users", users_post, methods=["POST"]),
        Route("/api/settings/users/{id:int}", user_put, methods=["PUT"]),
        Route("/api/settings/users/{id:int}", user_delete, methods=["DELETE"]),
        Route("/api/settings/users/{id:int}/password", user_password_post, methods=["POST"]),
        Route("/api/settings/audit-log", audit_log_get, methods=["GET"]),
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
