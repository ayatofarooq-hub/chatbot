"""Protected Starlette endpoints for application settings."""

from __future__ import annotations

import asyncio
import io
import json
import threading
from pathlib import Path

import httpx
import ollama
from starlette.concurrency import run_in_threadpool

try:
    from sqlalchemy.exc import IntegrityError
except ImportError:  # pragma: no cover - fallback for offline environments
    class IntegrityError(Exception):
        """Fallback exception used when SQLAlchemy is unavailable."""

        pass
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth import COOKIE_NAME, admin_for_token, audit, authenticate, revoke_token
from .build_index import main as build_index
from .settings_schema import SettingsValidationError, validate_settings
from .settings_store import (
    create_classification, delete_classification, get_settings,
    list_classifications, reassign_classification, reset_settings,
    update_classification, update_settings,
)
from .user_management import (
    audit_log, create_user, deactivate_user, list_users, reset_password,
    roles as user_roles, update_user,
)

_rebuild_lock = threading.Lock()
_rebuild_state = {"status": "idle", "detail": None}


def error(detail: str, status: int, code: str = "error", fields=None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "detail": detail, "fields": fields or {}}}, status_code=status)


def require_admin(request: Request, permission: str | None = None) -> dict | JSONResponse:
    admin = admin_for_token(request.cookies.get(COOKIE_NAME))
    if not admin:
        return error("Administrator authentication required.", 401, "unauthorized")
    if permission and permission not in admin.get("permissions", []):
        return error("Permission denied.", 403, "forbidden")
    return admin


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
        await run_in_threadpool(
            audit,
            "login_failed",
            target_type="admin_user",
            target_id=str(payload.get("username", "")),
            request=request,
        )
        return error("Invalid administrator credentials.", 401, "invalid_credentials")
    token, expires, remember_login = result
    admin = await run_in_threadpool(admin_for_token, token)
    await run_in_threadpool(audit, "login_success", actor=admin, request=request)
    response = JSONResponse({"authenticated": True})
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=request.url.scheme == "https",
        samesite="strict", expires=expires if remember_login else None, path="/",
    )
    return response


async def logout(request: Request) -> JSONResponse:
    admin = await run_in_threadpool(admin_for_token, request.cookies.get(COOKIE_NAME))
    await run_in_threadpool(revoke_token, request.cookies.get(COOKIE_NAME))
    await run_in_threadpool(audit, "logout", actor=admin, request=request)
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
    admin = require_admin(request, "manage_settings")
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        result = await run_in_threadpool(update_settings, payload)
        await run_in_threadpool(audit, "settings_updated", actor=admin, target_type="settings", details={"sections": list(payload)}, request=request)
        return JSONResponse(result)
    except SettingsValidationError as exc:
        return error("Settings validation failed.", 422, "validation_error", exc.errors)
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def settings_reset(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_settings")
    if isinstance(admin, Response):
        return admin
    result = await run_in_threadpool(reset_settings)
    await run_in_threadpool(audit, "settings_reset", actor=admin, target_type="settings", request=request)
    return JSONResponse(result)


async def classifications_get(request: Request) -> JSONResponse:
    admin = require_admin(request)
    if isinstance(admin, Response):
        return admin
    return JSONResponse({"items": await run_in_threadpool(list_classifications)})


async def classifications_post(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_classifications")
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(create_classification, await json_body(request))
        await run_in_threadpool(audit, "classification_created", actor=admin, target_type="classification", target_id=item["id"], request=request)
        return JSONResponse(item, status_code=201)
    except IntegrityError:
        return error("Arabic or English classification name already exists.", 409, "duplicate")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def classification_put(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_classifications")
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(update_classification, int(request.path_params["id"]), await json_body(request))
        await run_in_threadpool(audit, "classification_updated", actor=admin, target_type="classification", target_id=item["id"], request=request)
        return JSONResponse(item)
    except IntegrityError:
        return error("Arabic or English classification name already exists.", 409, "duplicate")
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def classification_delete(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_classifications")
    if isinstance(admin, Response):
        return admin
    try:
        await run_in_threadpool(delete_classification, int(request.path_params["id"]))
        await run_in_threadpool(audit, "classification_deleted", actor=admin, target_type="classification", target_id=request.path_params["id"], request=request)
        return JSONResponse({"deleted": True})
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 409, "classification_in_use")


async def classification_reassign(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_classifications")
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        count = await run_in_threadpool(
            reassign_classification, int(request.path_params["id"]), int(payload["target_id"])
        )
        await run_in_threadpool(
            audit, "classification_reassigned", actor=admin, target_type="classification",
            target_id=request.path_params["id"], details={"target_id": payload["target_id"], "count": count}, request=request,
        )
        return JSONResponse({"reassigned": count})
    except (KeyError, ValueError) as exc:
        return error(str(exc), 422, "validation_error")
    except LookupError as exc:
        return error(str(exc), 404, "not_found")


async def model_test(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_settings")
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
    admin = require_admin(request, "run_maintenance")
    if isinstance(admin, Response):
        return admin
    if _rebuild_state["status"] == "running":
        return error("An index rebuild is already running.", 409, "rebuild_running")
    threading.Thread(target=_run_rebuild, daemon=True).start()
    await run_in_threadpool(audit, "index_rebuild_started", actor=admin, target_type="search_index", request=request)
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
    admin = require_admin(request, "manage_settings")
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        if payload.get("version") != 1 or not isinstance(payload.get("settings"), dict):
            raise ValueError("Unsupported or invalid settings export.")
        validated = validate_settings(payload["settings"])
        result = await run_in_threadpool(update_settings, validated)
        await run_in_threadpool(audit, "settings_imported", actor=admin, target_type="settings", request=request)
        return JSONResponse(result)
    except SettingsValidationError as exc:
        return error("Imported settings failed validation.", 422, "validation_error", exc.errors)
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def backup_create(request: Request) -> JSONResponse:
    admin = require_admin(request, "run_maintenance")
    if isinstance(admin, Response):
        return admin
    return error(
        "Database-native backup is not configured. Export JSON backs up application settings only.",
        501, "not_configured",
    )


async def backup_restore(request: Request) -> JSONResponse:
    admin = require_admin(request, "run_maintenance")
    if isinstance(admin, Response):
        return admin
    return error("Database-native restore is not configured.", 501, "not_configured")


async def users_get(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_users")
    if isinstance(admin, Response):
        return admin
    return JSONResponse({"items": await run_in_threadpool(list_users), "roles": user_roles()})


async def users_post(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_users")
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(create_user, await json_body(request), admin)
        await run_in_threadpool(audit, "user_created", actor=admin, target_type="admin_user", target_id=item["id"], request=request)
        return JSONResponse(item, status_code=201)
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")
    except IntegrityError:
        return error("Username or email already exists.", 409, "duplicate")


async def user_put(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_users")
    if isinstance(admin, Response):
        return admin
    try:
        item = await run_in_threadpool(update_user, int(request.path_params["id"]), await json_body(request), admin)
        await run_in_threadpool(audit, "user_updated", actor=admin, target_type="admin_user", target_id=item["id"], request=request)
        return JSONResponse(item)
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")
    except IntegrityError:
        return error("Username or email already exists.", 409, "duplicate")


async def user_delete(request: Request) -> JSONResponse:
    admin = require_admin(request, "manage_users")
    if isinstance(admin, Response):
        return admin
    try:
        user_id = int(request.path_params["id"])
        if user_id == admin["id"]:
            return error("You cannot deactivate your own account.", 422, "validation_error")
        await run_in_threadpool(deactivate_user, user_id)
        await run_in_threadpool(audit, "user_deactivated", actor=admin, target_type="admin_user", target_id=user_id, request=request)
        return JSONResponse({"deleted": True})
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def user_password_post(request: Request) -> JSONResponse:
    admin = require_admin(request, "reset_passwords")
    if isinstance(admin, Response):
        return admin
    try:
        payload = await json_body(request)
        user_id = int(request.path_params["id"])
        password = str(payload.get("password", ""))
        await run_in_threadpool(reset_password, user_id, password)
        await run_in_threadpool(audit, "user_password_reset", actor=admin, target_type="admin_user", target_id=user_id, request=request)
        return JSONResponse({"reset": True})
    except LookupError as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc), 422, "validation_error")


async def audit_log_get(request: Request) -> JSONResponse:
    admin = require_admin(request, "view_audit_log")
    if isinstance(admin, Response):
        return admin
    limit = request.query_params.get("limit", "100")
    return JSONResponse({"items": await run_in_threadpool(audit_log, int(limit))})
