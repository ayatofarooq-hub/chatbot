"""Offline administrator password, roles, sessions, and audit logging."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt

from .settings_schema import DEFAULTS

COOKIE_NAME = "legal_admin_session"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_ROOT = PROJECT_ROOT / "data" / "metadata"
USERS_FILE = METADATA_ROOT / "admin_users.json"
SESSIONS_FILE = METADATA_ROOT / "admin_sessions.json"
AUDIT_FILE = METADATA_ROOT / "audit_log.json"

ROLES = {
    "super_admin": {
        "label": "Super administrator",
        "permissions": [
            "manage_settings",
            "manage_users",
            "reset_passwords",
            "view_audit_log",
            "manage_classifications",
            "run_maintenance",
        ],
    },
    "admin": {
        "label": "Administrator",
        "permissions": [
            "manage_settings",
            "reset_passwords",
            "view_audit_log",
            "manage_classifications",
            "run_maintenance",
        ],
    },
    "viewer": {
        "label": "Read-only reviewer",
        "permissions": ["view_audit_log"],
    },
}


def _ensure_files() -> None:
    METADATA_ROOT.mkdir(parents=True, exist_ok=True)
    for path in (USERS_FILE, SESSIONS_FILE, AUDIT_FILE):
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")


def _read_json(path: Path) -> list[dict]:
    _ensure_files()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _write_json(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def role_permissions(role: str) -> list[str]:
    return ROLES.get(role, ROLES["viewer"])["permissions"].copy()


def _policy(_: object | None = None) -> dict:
    return dict(DEFAULTS["authentication"])


def validate_password_policy(password: str, policy: dict | None = None) -> None:
    policy = policy or DEFAULTS["authentication"]
    minimum = int(policy.get("password_min_length") or 12)
    errors = []
    if len(password) < minimum:
        errors.append(f"at least {minimum} characters")
    if policy.get("require_numbers") and not any(char.isdigit() for char in password):
        errors.append("a number")
    if policy.get("require_symbols") and not any(not char.isalnum() for char in password):
        errors.append("a symbol")
    if policy.get("require_uppercase") and not any("A" <= char <= "Z" for char in password):
        errors.append("an uppercase Latin letter")
    if errors:
        raise ValueError("Administrator password must contain " + ", ".join(errors) + ".")


def audit(action: str, *, actor: dict | None = None, target_type: str | None = None, target_id: object | None = None, details: dict | None = None, request=None, engine=None) -> None:
    _ensure_files()
    entries = _read_json(AUDIT_FILE)
    entry = {
        "id": len(entries) + 1,
        "action": action,
        "actor_user_id": actor.get("id") if actor else None,
        "actor_username": actor.get("username") if actor else None,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "ip_address": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _write_json(AUDIT_FILE, entries)


def create_admin(username: str, password: str, engine=None) -> None:
    if not username.strip():
        raise ValueError("Administrator username cannot be empty.")
    validate_password_policy(password, _policy())
    users = _read_json(USERS_FILE)
    existing = next((user for user in users if user.get("username") == username.strip()), None)
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    if existing:
        existing.update({"password_hash": password_hash, "role": "super_admin", "is_active": True})
    else:
        users.append({
            "id": len(users) + 1,
            "username": username.strip(),
            "password_hash": password_hash,
            "role": "super_admin",
            "is_active": True,
            "display_name": username.strip(),
            "email": "",
        })
    _write_json(USERS_FILE, users)
    audit("admin_password_reset", actor={"username": "create_admin.py"}, target_type="admin_user", target_id=username.strip())


def authenticate(username: str, password: str, engine=None) -> tuple[str, datetime | None, bool] | None:
    users = _read_json(USERS_FILE)
    user = next((item for item in users if item.get("username") == username and item.get("is_active", True)), None)
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return None
    auth = DEFAULTS["authentication"]
    timeout = auth.get("session_timeout_minutes")
    expires = datetime.now(timezone.utc) + timedelta(minutes=timeout) if timeout else None
    token = secrets.token_urlsafe(48)
    sessions = _read_json(SESSIONS_FILE)
    sessions.append({
        "id": str(uuid.uuid4()),
        "admin_user_id": user["id"],
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "expires_at": expires.isoformat() if expires else None,
    })
    _write_json(SESSIONS_FILE, sessions)
    return token, expires, bool(auth.get("remember_login", False))


def admin_for_token(token: str | None, engine=None) -> dict | None:
    if not token:
        return None
    sessions = _read_json(SESSIONS_FILE)
    users = _read_json(USERS_FILE)
    users_by_id = {user["id"]: user for user in users}
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    for session in sessions:
        if session.get("token_hash") != token_hash:
            continue
        expires_at = session.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
            continue
        user = users_by_id.get(session.get("admin_user_id"))
        if not user or not user.get("is_active", True):
            continue
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
            "email": user.get("email", ""),
            "role": user.get("role", "admin"),
            "permissions": role_permissions(user.get("role", "admin")),
        }
    return None


def revoke_token(token: str | None, engine=None) -> None:
    if not token:
        return
    sessions = _read_json(SESSIONS_FILE)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    remaining = [session for session in sessions if session.get("token_hash") != token_hash]
    _write_json(SESSIONS_FILE, remaining)
