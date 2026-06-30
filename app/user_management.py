"""Administrator user CRUD, password reset, and audit-log persistence."""

from __future__ import annotations

from datetime import date, datetime

import bcrypt
from sqlalchemy import text

from .auth import ROLES, validate_password_policy
from .database import create_database_engine


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _json_row(row) -> dict:
    return {key: _json_value(value) for key, value in row.items()}


def _user_projection() -> str:
    return """
        id, username, display_name, email, role, is_active,
        created_at, updated_at, password_changed_at, last_login_at
    """


def roles() -> dict:
    return ROLES


def list_users(engine=None) -> list[dict]:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(f"""
                SELECT {_user_projection()}
                FROM public.admin_users
                ORDER BY is_active DESC, username
            """)).mappings()
            return [_json_row(row) for row in rows]
    finally:
        if own:
            engine.dispose()


def _password_policy(connection) -> dict:
    return dict(connection.execute(text("""
        SELECT password_min_length,require_numbers,require_symbols,require_uppercase
        FROM public.authentication_settings WHERE id=1
    """)).mappings().one())


def _assert_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError("Unsupported role.")


def _assert_last_super_admin_safe(connection, user_id: int, new_role: str | None = None, active: bool | None = None) -> None:
    row = connection.execute(text("""
        SELECT role,is_active FROM public.admin_users WHERE id=:id
    """), {"id": user_id}).mappings().one_or_none()
    if row is None:
        raise LookupError("User not found.")
    will_be_super = (new_role or row["role"]) == "super_admin"
    will_be_active = row["is_active"] if active is None else active
    if will_be_super and will_be_active:
        return
    count = connection.execute(text("""
        SELECT count(*) FROM public.admin_users
        WHERE id<>:id AND role='super_admin' AND is_active
    """), {"id": user_id}).scalar_one()
    if count == 0 and row["role"] == "super_admin" and row["is_active"]:
        raise ValueError("At least one active super administrator is required.")


def create_user(payload: dict, actor: dict | None = None, engine=None) -> dict:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "viewer")).strip()
    if not username:
        raise ValueError("Username is required.")
    _assert_role(role)
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            validate_password_policy(password, _password_policy(connection))
            row = connection.execute(text(f"""
                INSERT INTO public.admin_users
                (username,password_hash,display_name,email,role,is_active,created_by,password_changed_at)
                VALUES (:username,:password_hash,:display_name,:email,:role,:is_active,:created_by,now())
                RETURNING {_user_projection()}
            """), {
                "username": username,
                "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "display_name": str(payload.get("display_name") or "").strip() or None,
                "email": str(payload.get("email") or "").strip() or None,
                "role": role,
                "is_active": bool(payload.get("is_active", True)),
                "created_by": actor.get("id") if actor else None,
            }).mappings().one()
            return _json_row(row)
    finally:
        if own:
            engine.dispose()


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
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            _assert_last_super_admin_safe(
                connection,
                user_id,
                values.get("role"),
                values.get("is_active"),
            )
            assignments = ", ".join(f"{key}=:{key}" for key in values)
            row = connection.execute(text(f"""
                UPDATE public.admin_users
                SET {assignments}, updated_at=now()
                WHERE id=:user_id
                RETURNING {_user_projection()}
            """), {**values, "user_id": user_id}).mappings().one_or_none()
            if row is None:
                raise LookupError("User not found.")
            if values.get("is_active") is False:
                connection.execute(text(
                    "DELETE FROM public.admin_sessions WHERE admin_user_id=:user_id"
                ), {"user_id": user_id})
            return _json_row(row)
    finally:
        if own:
            engine.dispose()


def reset_password(user_id: int, password: str, engine=None) -> None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            validate_password_policy(password, _password_policy(connection))
            result = connection.execute(text("""
                UPDATE public.admin_users
                SET password_hash=:password_hash, password_changed_at=now(), updated_at=now()
                WHERE id=:user_id AND is_active
            """), {
                "user_id": user_id,
                "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            })
            if result.rowcount == 0:
                raise LookupError("Active user not found.")
            connection.execute(text(
                "DELETE FROM public.admin_sessions WHERE admin_user_id=:user_id"
            ), {"user_id": user_id})
    finally:
        if own:
            engine.dispose()


def deactivate_user(user_id: int, engine=None) -> None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            _assert_last_super_admin_safe(connection, user_id, active=False)
            result = connection.execute(text("""
                UPDATE public.admin_users
                SET is_active=false, updated_at=now()
                WHERE id=:user_id
            """), {"user_id": user_id})
            if result.rowcount == 0:
                raise LookupError("User not found.")
            connection.execute(text(
                "DELETE FROM public.admin_sessions WHERE admin_user_id=:user_id"
            ), {"user_id": user_id})
    finally:
        if own:
            engine.dispose()


def audit_log(limit: int = 100, engine=None) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT id, actor_user_id, actor_username, action, target_type,
                       target_id, ip_address::text AS ip_address, user_agent,
                       details, created_at
                FROM public.admin_audit_log
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"limit": limit}).mappings()
            return [_json_row(row) for row in rows]
    finally:
        if own:
            engine.dispose()
