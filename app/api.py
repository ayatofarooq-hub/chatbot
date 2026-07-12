"""HTTP API for testing the legal chatbot with clients such as Postman."""

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys
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
    from .rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from .search_index import search
    from .speech_to_text import inspect_audio, transcribe_audio
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
    from rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from search_index import search
    from speech_to_text import inspect_audio, transcribe_audio
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
    validated_results, _ = filter_results_to_registered(
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
        "warnings": list(dict.fromkeys(answer_result.warnings)),
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
        return JSONResponse({"deleted": True})
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
        Route("/ask", ask, methods=["POST"]),
        Route("/api/export-chat", export_chat, methods=["POST"]),
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
