"""JSON persistence for application-owned settings and classifications."""

from __future__ import annotations

from pathlib import Path

from .json_storage import read_json, write_json
from .settings_schema import DEFAULTS, validate_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_FILE = PROJECT_ROOT / "data" / "metadata.json"


def _ensure_metadata() -> None:
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not METADATA_FILE.exists():
        write_json(METADATA_FILE, {"settings": DEFAULTS, "classifications": []})


def _metadata() -> dict:
    _ensure_metadata()
    payload = read_json(METADATA_FILE, {})
    return payload if isinstance(payload, dict) else {}


def _write_metadata(payload: dict) -> None:
    write_json(METADATA_FILE, payload)


def get_settings(engine=None) -> dict:
    payload = dict(_metadata().get("settings") or {})
    result = {section: dict(value) for section, value in DEFAULTS.items() if isinstance(value, dict)}
    for section, value in payload.items():
        if isinstance(value, dict):
            result[section] = {**result.get(section, {}), **value}
    result["capabilities"] = {
        "fine_tuning": True,
        "upload_endpoint": False,
        "automatic_backup_scheduler": False,
        "desktop_notifications": False,
    }
    return result


def update_settings(payload: dict, engine=None) -> dict:
    changes = validate_settings(payload)
    metadata = _metadata()
    existing = dict(metadata.get("settings") or {})
    for section, values in changes.items():
        if values:
            existing[section] = {**existing.get(section, {}), **values}
    metadata["settings"] = existing
    _write_metadata(metadata)
    return get_settings()


def reset_settings(engine=None) -> dict:
    metadata = _metadata()
    metadata["settings"] = DEFAULTS
    _write_metadata(metadata)
    return get_settings()


def list_classifications(engine=None) -> list[dict]:
    rows = list(_metadata().get("classifications") or [])
    return [dict(row) for row in rows if isinstance(row, dict)]


def create_classification(payload: dict, engine=None) -> dict:
    required = ("name_ar", "name_en")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise ValueError("Arabic and English names are required.")
    rows = list(list_classifications())
    if any(row.get("name_ar") == payload["name_ar"].strip() or row.get("name_en") == payload["name_en"].strip() for row in rows):
        raise ValueError("Classification already exists.")
    item = {
        "id": max([int(row.get("id", 0)) for row in rows] or [0]) + 1,
        "source_value": payload["name_ar"].strip(),
        "name_ar": payload["name_ar"].strip(),
        "name_en": payload["name_en"].strip(),
        "description": str(payload.get("description", "")).strip(),
        "icon_identifier": str(payload.get("icon_identifier", "document")).strip(),
        "color": payload.get("color", "#145a38"),
        "enabled": bool(payload.get("enabled", True)),
        "display_order": int(payload.get("display_order", 0)),
    }
    rows.append(item)
    metadata = _metadata()
    metadata["classifications"] = rows
    _write_metadata(metadata)
    return item


def update_classification(classification_id: int, payload: dict, engine=None) -> dict:
    rows = [dict(row) for row in list_classifications()]
    item = next((row for row in rows if int(row.get("id", 0)) == classification_id), None)
    if item is None:
        raise LookupError("Classification not found.")
    allowed = {"name_ar", "name_en", "description", "icon_identifier", "color", "enabled", "display_order"}
    values = {key: value for key, value in payload.items() if key in allowed}
    if not values:
        raise ValueError("No supported fields supplied.")
    item.update(values)
    metadata = _metadata()
    metadata["classifications"] = rows
    _write_metadata(metadata)
    return item


def delete_classification(classification_id: int, engine=None) -> None:
    rows = [dict(row) for row in list_classifications()]
    remaining = [row for row in rows if int(row.get("id", 0)) != classification_id]
    if len(remaining) == len(rows):
        raise LookupError("Classification not found.")
    metadata = _metadata()
    metadata["classifications"] = remaining
    _write_metadata(metadata)


def reassign_classification(source_id: int, target_id: int, engine=None) -> int:
    if source_id == target_id:
        raise ValueError("Source and target must differ.")
    return 0
