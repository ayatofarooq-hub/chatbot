"""Administrator user CRUD, password reset, and audit-log persistence."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import bcrypt

from .auth import ROLES, validate_password_policy
from .json_storage import read_json, write_json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_FILE = PROJECT_ROOT / "data" / "metadata.json"


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json_row(row) -> dict:
    return {key: _json_value(value) for key, value in row.items()}


def _ensure_files() -> None:
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        write_json(METADATA_FILE, {})


def _metadata() -> dict:
    _ensure_files()
    payload = read_json(METADATA_FILE, {})
    return payload if isinstance(payload, dict) else {}


def _read_list(section: str) -> list[dict]:
    rows = _metadata().get(section) or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _write_list(section: str, payload: list[dict]) -> None:
    metadata = _metadata()
    metadata[section] = payload
    write_json(METADATA_FILE, metadata)


def roles() -> dict:
    return ROLES


def list_users(engine=None) -> list[dict]:
    users = _read_list("admin_users")
    return [_json_row({key: user.get(key) for key in user}) for user in users]


def _assert_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError("Unsupported role.")


def _assert_last_super_admin_safe(user_id: int, new_role: str | None = None, active: bool | None = None) -> None:
    users = _read_list("admin_users")
    row = next((user for user in users if user.get("id") == user_id), None)
    if row is None:
        raise LookupError("User not found.")
    will_be_super = (new_role or row.get("role")) == "super_admin"
    will_be_active = row.get("is_active") if active is None else active
    if will_be_super and will_be_active:
        return
    if sum(1 for user in users if user.get("role") == "super_admin" and user.get("is_active", True) and user.get("id") != user_id) == 0 and row.get("role") == "super_admin" and row.get("is_active", True):
        raise ValueError("At least one active super administrator is required.")


def create_user(payload: dict, actor: dict | None = None, engine=None) -> dict:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "viewer")).strip()
    if not username:
        raise ValueError("Username is required.")
    _assert_role(role)
    users = _read_list("admin_users")
    if any(user.get("username") == username for user in users):
        raise ValueError("Username already exists.")
    user = {
        "id": max([int(user.get("id", 0)) for user in users] or [0]) + 1,
        "username": username,
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "display_name": str(payload.get("display_name") or "").strip() or None,
        "email": str(payload.get("email") or "").strip() or None,
        "role": role,
        "is_active": bool(payload.get("is_active", True)),
        "created_by": actor.get("id") if actor else None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "password_changed_at": datetime.now().isoformat(),
        "last_login_at": None,
    }
    users.append(user)
    _write_list("admin_users", users)
    return _json_row(user)


def update_user(user_id: int, payload: dict, actor: dict | None = None, engine=None) -> dict:
    allowed = {"display_name", "email", "role", "is_active"}
    values = {key: payload[key] for key in allowed if key in payload}
    if not values:
        raise ValueError("No supported user fields supplied.")
    if "role" in values:
        values["role"] = str(values["role"]).strip()
        _assert_role(values["role"])
    if "display_name" in values:
        values["display_name"] = str(values["display_name"] or "").strip() or None
    if "email" in values:
        values["email"] = str(values["email"] or "").strip() or None
    if "is_active" in values:
        values["is_active"] = bool(values["is_active"])
    users = _read_list("admin_users")
    user = next((item for item in users if item.get("id") == user_id), None)
    if user is None:
        raise LookupError("User not found.")
    _assert_last_super_admin_safe(user_id, values.get("role"), values.get("is_active"))
    user.update(values)
    user["updated_at"] = datetime.now().isoformat()
    _write_list("admin_users", users)
    return _json_row(user)


def reset_password(user_id: int, password: str, engine=None) -> None:
    users = _read_list("admin_users")
    user = next((item for item in users if item.get("id") == user_id and item.get("is_active", True)), None)
    if user is None:
        raise LookupError("Active user not found.")
    validate_password_policy(password)
    user["password_hash"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user["password_changed_at"] = datetime.now().isoformat()
    user["updated_at"] = datetime.now().isoformat()
    _write_list("admin_users", users)


def deactivate_user(user_id: int, engine=None) -> None:
    users = _read_list("admin_users")
    user = next((item for item in users if item.get("id") == user_id), None)
    if user is None:
        raise LookupError("User not found.")
    _assert_last_super_admin_safe(user_id, active=False)
    user["is_active"] = False
    user["updated_at"] = datetime.now().isoformat()
    _write_list("admin_users", users)


def audit_log(
    limit: int = 100,
    offset: int = 0,
    engine=None,
) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    rows = _read_list("audit_log")
    newest_first = [dict(row) for row in reversed(rows)]
    return newest_first[offset : offset + limit]


def audit_log_count(engine=None) -> int:
    return len(_read_list("audit_log"))
