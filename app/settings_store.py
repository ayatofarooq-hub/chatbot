"""PostgreSQL persistence for application-owned settings and classifications."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import text

from .database import create_database_engine
from .settings_schema import DEFAULTS, validate_settings

TABLES = {
    "model": "model_settings", "retrieval": "retrieval_settings",
    "authentication": "authentication_settings", "appearance": "appearance_settings",
    "upload": "upload_settings", "notifications": "notification_settings",
    "backup": "backup_settings", "fine_tuning": "fine_tuning_settings",
}

READ_ONLY_COLUMNS = {
    "fine_tuning": {"live_model_run_id", "live_model_id"},
}


def _json_row(row) -> dict:
    return {
        key: value.strftime("%H:%M") if isinstance(value, time)
        else value.isoformat() if isinstance(value, (date, datetime)) else value
        for key, value in row.items()
    }


def _setting_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return value


def get_settings(engine=None) -> dict:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        result = {}
        with engine.connect() as connection:
            for section, table in TABLES.items():
                row = connection.execute(text(f"SELECT * FROM public.{table} WHERE id=1")).mappings().one()
                result[section] = {
                    key: _setting_value(value)
                    for key, value in row.items()
                    if key in DEFAULTS[section]
                    and key not in {"id", "updated_at"} | READ_ONLY_COLUMNS.get(section, set())
                }
        result["capabilities"] = {
            "fine_tuning": True, "upload_endpoint": False,
            "automatic_backup_scheduler": False, "desktop_notifications": False,
        }
        return result
    finally:
        if own:
            engine.dispose()


def update_settings(payload: dict, engine=None) -> dict:
    changes = validate_settings(payload)
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            for section, values in changes.items():
                if not values:
                    continue
                writable = {
                    key: value
                    for key, value in values.items()
                    if key not in READ_ONLY_COLUMNS.get(section, set())
                }
                if not writable:
                    continue
                assignments = ", ".join(f"{key}=:{key}" for key in writable)
                connection.execute(
                    text(f"UPDATE public.{TABLES[section]} SET {assignments}, updated_at=now() WHERE id=1"),
                    writable,
                )
        return get_settings(engine)
    finally:
        if own:
            engine.dispose()


def reset_settings(engine=None) -> dict:
    return update_settings(DEFAULTS, engine)


def list_classifications(engine=None) -> list[dict]:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT c.*, count(l.id) AS law_count
                FROM public.document_classifications c
                LEFT JOIN public.iraqi_laws l ON l.classification=c.source_value
                WHERE c.deleted_at IS NULL GROUP BY c.id ORDER BY c.display_order, c.id
            """)).mappings()
            return [
                _json_row({k: v for k, v in row.items() if k != "deleted_at"})
                for row in rows
            ]
    finally:
        if own:
            engine.dispose()


def create_classification(payload: dict, engine=None) -> dict:
    required = ("name_ar", "name_en")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise ValueError("Arabic and English names are required.")
    own = engine is None
    engine = engine or create_database_engine()
    values = {
        "source_value": payload["name_ar"].strip(), "name_ar": payload["name_ar"].strip(),
        "name_en": payload["name_en"].strip(), "description": str(payload.get("description", "")).strip(),
        "icon_identifier": str(payload.get("icon_identifier", "document")).strip(),
        "color": payload.get("color", "#145a38"), "enabled": bool(payload.get("enabled", True)),
        "display_order": int(payload.get("display_order", 0)),
    }
    try:
        with engine.begin() as connection:
            row = connection.execute(text("""
                INSERT INTO public.document_classifications
                (source_value,name_ar,name_en,description,icon_identifier,color,enabled,display_order)
                VALUES (:source_value,:name_ar,:name_en,:description,:icon_identifier,:color,:enabled,:display_order)
                RETURNING *
            """), values).mappings().one()
        return _json_row(row)
    finally:
        if own:
            engine.dispose()


def update_classification(classification_id: int, payload: dict, engine=None) -> dict:
    allowed = {"name_ar", "name_en", "description", "icon_identifier", "color", "enabled", "display_order"}
    values = {key: value for key, value in payload.items() if key in allowed}
    if not values:
        raise ValueError("No supported fields supplied.")
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            assignments = ", ".join(f"{key}=:{key}" for key in values)
            row = connection.execute(text(
                f"UPDATE public.document_classifications SET {assignments}, updated_at=now() "
                "WHERE id=:classification_id AND deleted_at IS NULL RETURNING *"
            ), {**values, "classification_id": classification_id}).mappings().one_or_none()
            if row is None:
                raise LookupError("Classification not found.")
        return _json_row(row)
    finally:
        if own:
            engine.dispose()


def delete_classification(classification_id: int, engine=None) -> None:
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            row = connection.execute(text("""
                SELECT c.source_value, count(l.id) law_count
                FROM public.document_classifications c
                LEFT JOIN public.iraqi_laws l ON l.classification=c.source_value
                WHERE c.id=:id AND c.deleted_at IS NULL GROUP BY c.source_value
            """), {"id": classification_id}).mappings().one_or_none()
            if row is None:
                raise LookupError("Classification not found.")
            if row["law_count"]:
                raise ValueError(f"Classification is used by {row['law_count']} legal records; reassign first.")
            connection.execute(text(
                "UPDATE public.document_classifications SET deleted_at=now(), updated_at=now() WHERE id=:id"
            ), {"id": classification_id})
    finally:
        if own:
            engine.dispose()


def reassign_classification(source_id: int, target_id: int, engine=None) -> int:
    if source_id == target_id:
        raise ValueError("Source and target must differ.")
    own = engine is None
    engine = engine or create_database_engine()
    try:
        with engine.begin() as connection:
            rows = connection.execute(text("""
                SELECT id, source_value FROM public.document_classifications
                WHERE id IN (:source_id,:target_id) AND deleted_at IS NULL FOR UPDATE
            """), {"source_id": source_id, "target_id": target_id}).mappings().all()
            by_id = {row["id"]: row["source_value"] for row in rows}
            if source_id not in by_id or target_id not in by_id:
                raise LookupError("Source or target classification not found.")
            result = connection.execute(text("""
                UPDATE public.iraqi_laws SET classification=:target
                WHERE classification=:source
            """), {"source": by_id[source_id], "target": by_id[target_id]})
            connection.execute(text(
                "UPDATE public.document_classifications SET deleted_at=now(), updated_at=now() WHERE id=:id"
            ), {"id": source_id})
            return result.rowcount
    finally:
        if own:
            engine.dispose()
