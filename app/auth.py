"""Server-side administrator password, roles, sessions, and audit logging."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import text

from .database import create_database_engine
from .settings_schema import DEFAULTS

COOKIE_NAME = "legal_admin_session"

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


def role_permissions(role: str) -> list[str]:
    return ROLES.get(role, ROLES["viewer"])["permissions"].copy()


def _policy(connection) -> dict:
    try:
        row = connection.execute(text("""
            SELECT password_min_length,require_numbers,require_symbols,require_uppercase
            FROM public.authentication_settings WHERE id=1
        """)).mappings().one_or_none()
    except Exception:
        row = None
    return dict(row or DEFAULTS["authentication"])


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


def audit(
    action: str,
    *,
    actor: dict | None = None,
    target_type: str | None = None,
    target_id: object | None = None,
    details: dict | None = None,
    request=None,
    engine=None,
) -> None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO public.admin_audit_log
                (actor_user_id,actor_username,action,target_type,target_id,ip_address,user_agent,details)
                VALUES (:actor_user_id,:actor_username,:action,:target_type,:target_id,
                        CAST(:ip_address AS inet),:user_agent,CAST(:details AS jsonb))
            """), {
                "actor_user_id": actor.get("id") if actor else None,
                "actor_username": actor.get("username") if actor else None,
                "action": action,
                "target_type": target_type,
                "target_id": str(target_id) if target_id is not None else None,
                "ip_address": request.client.host if request and request.client else None,
                "user_agent": request.headers.get("user-agent") if request else None,
                "details": __import__("json").dumps(details or {}),
            })
    except Exception:
        # Audit logging must not break the primary operation.
        pass
    finally:
        if own:
            engine.dispose()


def create_admin(username: str, password: str, engine=None) -> None:
    if not username.strip():
        raise ValueError("Administrator username cannot be empty.")
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            validate_password_policy(password, _policy(connection))
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            connection.execute(text("""
                INSERT INTO public.admin_users (username,password_hash,role,password_changed_at)
                VALUES (:username,:password_hash,'super_admin',now())
                ON CONFLICT (username) DO UPDATE SET password_hash=excluded.password_hash,
                    role='super_admin', is_active=true, password_changed_at=now(), updated_at=now()
            """), {"username": username.strip(), "password_hash": password_hash})
            audit(
                "admin_password_reset",
                actor={"username": "create_admin.py"},
                target_type="admin_user",
                target_id=username.strip(),
                engine=engine,
            )
    finally:
        if own:
            engine.dispose()


def authenticate(username: str, password: str, engine=None) -> tuple[str, datetime | None, bool] | None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            user = connection.execute(text(
                "SELECT id,username,password_hash,role FROM public.admin_users WHERE username=:username AND is_active"
            ), {"username": username}).mappings().one_or_none()
            if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
            connection.execute(text(
                "UPDATE public.admin_users SET last_login_at=now(), updated_at=now() WHERE id=:id"
            ), {"id": user["id"]})
            auth = connection.execute(text(
                "SELECT session_timeout_minutes,remember_login FROM public.authentication_settings WHERE id=1"
            )).mappings().one()
            timeout = auth["session_timeout_minutes"]
            expires = datetime.now(timezone.utc) + timedelta(minutes=timeout) if timeout else None
            token = secrets.token_urlsafe(48)
            connection.execute(text("""
                INSERT INTO public.admin_sessions (id,admin_user_id,token_hash,expires_at)
                VALUES (:id,:user_id,:token_hash,:expires_at)
            """), {
                "id": uuid.uuid4(), "user_id": user["id"],
                "token_hash": hashlib.sha256(token.encode()).hexdigest(), "expires_at": expires,
            })
            return token, expires, auth["remember_login"]
    finally:
        if own:
            engine.dispose()


def admin_for_token(token: str | None, engine=None) -> dict | None:
    if not token:
        return None
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            row = connection.execute(text("""
                SELECT u.id,u.username,u.display_name,u.email,u.role,s.id session_id
                FROM public.admin_sessions s JOIN public.admin_users u ON u.id=s.admin_user_id
                WHERE s.token_hash=:token_hash AND u.is_active
                  AND (s.expires_at IS NULL OR s.expires_at > now())
            """), {"token_hash": hashlib.sha256(token.encode()).hexdigest()}).mappings().one_or_none()
            if row:
                connection.execute(text(
                    "UPDATE public.admin_sessions SET last_seen_at=now() WHERE id=:id"
                ), {"id": row["session_id"]})
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "email": row["email"],
                    "role": row["role"],
                    "permissions": role_permissions(row["role"]),
                }
            return None
    finally:
        if own:
            engine.dispose()


def revoke_token(token: str | None, engine=None) -> None:
    if not token:
        return
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "DELETE FROM public.admin_sessions WHERE token_hash=:token_hash"
            ), {"token_hash": hashlib.sha256(token.encode()).hexdigest()})
    finally:
        if own:
            engine.dispose()
