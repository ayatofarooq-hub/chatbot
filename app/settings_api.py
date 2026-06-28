"""Protected Starlette endpoints for application settings."""

from __future__ import annotations

import asyncio
import io
import json
import threading
from pathlib import Path

import httpx
import ollama
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth import COOKIE_NAME, admin_for_token, authenticate, revoke_token
from .build_index import main as build_index
from .settings_schema import SettingsValidationError, validate_settings
from .settings_store import (
    create_classification, delete_classification, get_settings,
    list_classifications, reassign_classification, reset_settings,
    update_classification, update_settings,
)

_rebuild_lock = threading.Lock()
_rebuild_state = {"status": "idle", "detail": None}


def error(detail: str, status: int, code: str = "error", fields=None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "detail": detail, "fields": fields or {}}}, status_code=status)


def require_admin(request: Request) -> dict | JSONResponse:
    admin = admin_for_token(request.cookies.get(COOKIE_NAME))
    return admin or error("Administrator authentication required.", 401, "unauthorized")


async def json_body(request: Request) -> dict:
    try:
        value = await request.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


async def login(request: Request) -> JSONResponse:
    try:
        payload = await json_body(request)
        result = await run_in_threadpool(authenticate, str(payload.get("username", "")), str(payload.get("password", "")))
    except ValueError as exc:
        return error(str(exc), 400, "invalid_json")
    if not result:
        return error("Invalid administrator credentials.", 401, "invalid_credentials")
    token, expires, remember_login = result
    response = JSONResponse({"authenticated": True})
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=request.url.scheme == "https",
        samesite="strict", expires=expires if remember_login else None, path="/",
    )
    return response


async def logout(request: Request) -> JSONResponse:
    await run_in_threadpool(revoke_token, request.cookies.get(COOKIE_NAME))
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


async def session(request: Request) -> JSONResponse:
    admin = await run_in_threadpool(admin_for_token, request.cookies.get(COOKIE_NAME))
    return JSONResponse({"authenticated": bool(admin), "administrator": admin})


async def settings_get(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return JSONResponse(await run_in_threadpool(get_settings))


async def settings_put(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        return JSONResponse(await run_in_threadpool(update_settings, await json_body(request)))
    except SettingsValidationError as exc:
        return error("Settings validation failed.", 422, "validation_error", exc.errors)
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def settings_reset(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return JSONResponse(await run_in_threadpool(reset_settings))


async def classifications_get(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return JSONResponse({"items": await run_in_threadpool(list_classifications)})


async def classifications_post(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(create_classification, await json_body(request))
        return JSONResponse(item, status_code=201)
    except IntegrityError:
        return error("Arabic or English classification name already exists.", 409, "duplicate")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def classification_put(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(update_classification, int(request.path_params["id"]), await json_body(request))
        return JSONResponse(item)
    except IntegrityError:
        return error("Arabic or English classification name already exists.", 409, "duplicate")
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def classification_delete(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        await run_in_threadpool(delete_classification, int(request.path_params["id"]))
        return JSONResponse({"deleted": True})
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 409, "classification_in_use")


async def classification_reassign(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        count = await run_in_threadpool(
            reassign_classification, int(request.path_params["id"]), int(payload["target_id"])
        )
        return JSONResponse({"reassigned": count})
    except (KeyError, ValueError) as exc:
        return error(str(exc), 422, "validation_error")
    except LookupError as exc:
        return error(str(exc), 404, "not_found")


async def model_test(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        current = get_settings()["model"]
        base_url = payload.get("ollama_base_url", current["ollama_base_url"])
        timeout = payload.get("request_timeout", current["request_timeout"])
        client = ollama.Client(host=base_url, timeout=timeout)
        models = await run_in_threadpool(client.list)
        return JSONResponse({"ok": True, "model_count": len(models.models)})
    except (httpx.HTTPError, ollama.ResponseError, OSError, ValueError) as exc:
        return error(f"Ollama connection failed: {exc}", 503, "ollama_unavailable")


def _run_rebuild() -> None:
    if not _rebuild_lock.acquire(blocking=False):
        return
    try:
        _rebuild_state.update(status="running", detail=None)
        build_index()
        _rebuild_state.update(status="completed", detail=None)
    except BaseException as exc:  # build_index.main uses SystemExit on failure
        _rebuild_state.update(status="failed", detail=str(exc))
    finally:
        _rebuild_lock.release()


async def index_rebuild(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    if _rebuild_state["status"] == "running":
        return error("An index rebuild is already running.", 409, "rebuild_running")
    threading.Thread(target=_run_rebuild, daemon=True).start()
    return JSONResponse({"status": "running"}, status_code=202)


async def index_status(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return JSONResponse(_rebuild_state)


async def settings_export(request: Request) -> Response:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    payload = {"version": 1, "settings": get_settings(), "classifications": list_classifications()}
    payload["settings"].pop("capabilities", None)
    return Response(
        json.dumps(payload, ensure_ascii=False, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="application-settings.json"'},
    )


async def settings_import(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        if payload.get("version") != 1 or not isinstance(payload.get("settings"), dict):
            raise ValueError("Unsupported or invalid settings export.")
        validated = validate_settings(payload["settings"])
        return JSONResponse(await run_in_threadpool(update_settings, validated))
    except SettingsValidationError as exc:
        return error("Imported settings failed validation.", 422, "validation_error", exc.errors)
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def backup_create(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return error(
        "Database-native backup is not configured. Export JSON backs up application settings only.",
        501, "not_configured",
    )


async def backup_restore(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return error("Database-native restore is not configured.", 501, "not_configured")
