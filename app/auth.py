"""Server-side administrator password and session authentication."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import text

from .database import create_database_engine

COOKIE_NAME = "legal_admin_session"


def create_admin(username: str, password: str, engine=None) -> None:
    if len(password) < 12:
        raise ValueError("Administrator password must contain at least 12 characters.")
    own = engine is None
    engine = engine or create_database_engine()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO public.admin_users (username,password_hash)
                VALUES (:username,:password_hash)
                ON CONFLICT (username) DO UPDATE SET password_hash=excluded.password_hash,
                    is_active=true, updated_at=now()
            """), {"username": username.strip(), "password_hash": password_hash})
    finally:
        if own:
            engine.dispose()


def authenticate(username: str, password: str, engine=None) -> tuple[str, datetime | None, bool] | None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            user = connection.execute(text(
                "SELECT id,password_hash FROM public.admin_users WHERE username=:username AND is_active"
            ), {"username": username}).mappings().one_or_none()
            if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
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
                SELECT u.id,u.username,s.id session_id
                FROM public.admin_sessions s JOIN public.admin_users u ON u.id=s.admin_user_id
                WHERE s.token_hash=:token_hash AND u.is_active
                  AND (s.expires_at IS NULL OR s.expires_at > now())
            """), {"token_hash": hashlib.sha256(token.encode()).hexdigest()}).mappings().one_or_none()
            if row:
                connection.execute(text(
                    "UPDATE public.admin_sessions SET last_seen_at=now() WHERE id=:id"
                ), {"id": row["session_id"]})
                return {"id": row["id"], "username": row["username"]}
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
