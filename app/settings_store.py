"""JSON persistence for application-owned settings and classifications."""

from __future__ import annotations

import json
from pathlib import Path

from .settings_schema import DEFAULTS, validate_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_ROOT = PROJECT_ROOT / "data" / "metadata"
SETTINGS_FILE = METADATA_ROOT / "settings.json"
CLASSIFICATIONS_FILE = METADATA_ROOT / "classifications.json"


def _ensure_metadata() -> None:
    METADATA_ROOT.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not CLASSIFICATIONS_FILE.exists():
        CLASSIFICATIONS_FILE.write_text("[]\n", encoding="utf-8")


def _read_json(path: Path) -> object:
    _ensure_metadata()
    if not path.exists():
        return [] if path.suffix == ".json" and path.name == "classifications.json" else {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_settings(engine=None) -> dict:
    payload = dict(_read_json(SETTINGS_FILE))
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
    existing = dict(_read_json(SETTINGS_FILE))
    for section, values in changes.items():
        if values:
            existing[section] = {**existing.get(section, {}), **values}
    _write_json(SETTINGS_FILE, existing)
    return get_settings()


def reset_settings(engine=None) -> dict:
    _write_json(SETTINGS_FILE, DEFAULTS)
    return get_settings()


def list_classifications(engine=None) -> list[dict]:
    rows = list(_read_json(CLASSIFICATIONS_FILE))
    return [dict(row) for row in rows if isinstance(row, dict)]


def create_classification(payload: dict, engine=None) -> dict:
    required = ("name_ar", "name_en")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise ValueError("Arabic and English names are required.")
    rows = list(list_classifications())
    if any(row.get("name_ar") == payload["name_ar"].strip() or row.get("name_en") == payload["name_en"].strip() for row in rows):
        raise ValueError("Classification already exists.")
    item = {
        "id": len(rows) + 1,
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
    _write_json(CLASSIFICATIONS_FILE, rows)
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
    _write_json(CLASSIFICATIONS_FILE, rows)
    return item


def delete_classification(classification_id: int, engine=None) -> None:
    rows = [dict(row) for row in list_classifications()]
    remaining = [row for row in rows if int(row.get("id", 0)) != classification_id]
    if len(remaining) == len(rows):
        raise LookupError("Classification not found.")
    _write_json(CLASSIFICATIONS_FILE, remaining)


def reassign_classification(source_id: int, target_id: int, engine=None) -> int:
    if source_id == target_id:
        raise ValueError("Source and target must differ.")
    return 0
