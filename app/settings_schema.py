"""Validation and defaults for administrator-managed settings."""

from __future__ import annotations

import re
from copy import deepcopy


DEFAULTS = {
    "model": {
        "chat_model": "qwen2.5:3b", "embedding_model": "bge-m3",
        "ollama_base_url": "http://127.0.0.1:11434", "request_timeout": 600,
        "keep_alive": "10m", "max_answer_tokens": 192, "temperature": 0.0,
        "top_p": 0.9, "context_length": 4096,
    },
    "retrieval": {
        "chunk_size": 1100, "chunk_overlap": 120, "semantic_weight": 0.7,
        "keyword_weight": 0.3, "result_count": 5, "hybrid_search": True,
        "debug_context": False, "ocr_enabled": True, "ocr_language": "ara",
    },
    "authentication": {
        "login_enabled": True, "remember_login": True,
        "session_timeout_minutes": 60, "password_min_length": 12,
        "require_numbers": True, "require_symbols": False,
        "require_uppercase": False,
    },
    "appearance": {
        "language": "ar", "theme": "system", "primary_color": "green",
        "custom_primary_color": None, "interface_scale": "medium",
    },
    "upload": {
        "max_file_size_mb": 20, "max_file_count": 3, "allow_docx": True,
        "allow_pdf": True, "allow_txt": True, "ocr_enabled": True,
        "ocr_language": "ara",
    },
    "notifications": {
        "browser_notifications": False, "processing_completed": True,
        "upload_failed": True, "model_error": True,
        "index_rebuild_completed": True, "json_backup_completed": True,
    },
    "backup": {"automatic_frequency": None, "local_destination": None},
    "fine_tuning": {
        "learning_mode": "manual", "auto_approval_threshold": 0.85,
        "validation_threshold": 0.80, "scheduled_start_time": "02:00",
        "system_signed_in": True,
    },
}

RANGES = {
    ("model", "request_timeout"): (5, 1800),
    ("model", "max_answer_tokens"): (64, 8192),
    ("model", "temperature"): (0, 2),
    ("model", "top_p"): (0.001, 1),
    ("model", "context_length"): (1024, 131072),
    ("retrieval", "chunk_size"): (200, 10000),
    ("retrieval", "chunk_overlap"): (0, 9999),
    ("retrieval", "semantic_weight"): (0, 1),
    ("retrieval", "keyword_weight"): (0, 1),
    ("retrieval", "result_count"): (1, 50),
    ("authentication", "password_min_length"): (8, 128),
    ("upload", "max_file_size_mb"): (1, 500),
    ("upload", "max_file_count"): (1, 50),
    ("fine_tuning", "auto_approval_threshold"): (0, 1),
    ("fine_tuning", "validation_threshold"): (0, 1),
}
ENUMS = {
    ("retrieval", "ocr_language"): {"ara", "eng", "ara+eng"},
    ("authentication", "session_timeout_minutes"): {15, 30, 60, 240, None},
    ("appearance", "language"): {"ar", "en"},
    ("appearance", "theme"): {"light", "dark", "system"},
    ("appearance", "primary_color"): {"green", "gold", "blue", "custom"},
    ("appearance", "interface_scale"): {"small", "medium", "large"},
    ("upload", "max_file_size_mb"): {5, 10, 20, 25},
    ("upload", "ocr_language"): {"ara", "eng", "ara+eng"},
    ("backup", "automatic_frequency"): {"daily", "weekly", "monthly", None},
    ("fine_tuning", "learning_mode"): {"manual", "automatic"},
}


class SettingsValidationError(ValueError):
    """A settings payload failed validation."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("Settings validation failed.")
        self.errors = errors


def validate_settings(payload: object, partial: bool = True) -> dict:
    if not isinstance(payload, dict):
        raise SettingsValidationError({"body": "Expected a JSON object."})
    result = deepcopy(DEFAULTS) if not partial else {}
    errors = {}
    for section, values in payload.items():
        if section not in DEFAULTS or not isinstance(values, dict):
            errors[section] = "Unknown section or invalid object."
            continue
        result.setdefault(section, {})
        for key, value in values.items():
            path = (section, key)
            if key not in DEFAULTS[section]:
                errors[f"{section}.{key}"] = "Unknown setting."
                continue
            expected = DEFAULTS[section][key]
            if expected is not None and isinstance(expected, bool):
                valid_type = isinstance(value, bool)
            elif expected is not None and isinstance(expected, int):
                valid_type = isinstance(value, int) and not isinstance(value, bool)
            elif expected is not None and isinstance(expected, float):
                valid_type = isinstance(value, (int, float)) and not isinstance(value, bool)
            else:
                valid_type = value is None or isinstance(value, str)
            if not valid_type:
                errors[f"{section}.{key}"] = "Invalid value type."
                continue
            if path in RANGES and not RANGES[path][0] <= value <= RANGES[path][1]:
                errors[f"{section}.{key}"] = f"Must be between {RANGES[path][0]} and {RANGES[path][1]}."
            elif path in ENUMS and value not in ENUMS[path]:
                errors[f"{section}.{key}"] = "Unsupported value."
            else:
                result[section][key] = value
    retrieval = result.get("retrieval", {})
    if retrieval:
        merged = {**DEFAULTS["retrieval"], **retrieval}
        if merged["chunk_overlap"] >= merged["chunk_size"]:
            errors["retrieval.chunk_overlap"] = "Must be smaller than chunk size."
        if abs(merged["semantic_weight"] + merged["keyword_weight"] - 1) > 0.001:
            errors["retrieval.weights"] = "Semantic and keyword weights must total 1."
    appearance = result.get("appearance", {})
    if appearance.get("custom_primary_color") is not None and not re.fullmatch(
        r"#[0-9A-Fa-f]{6}", appearance["custom_primary_color"]
    ):
        errors["appearance.custom_primary_color"] = "Use #RRGGBB format."
    fine_tuning = result.get("fine_tuning", {})
    if fine_tuning.get("scheduled_start_time") is not None and not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", fine_tuning["scheduled_start_time"]
    ):
        errors["fine_tuning.scheduled_start_time"] = "Use HH:MM 24-hour format."
    if errors:
        raise SettingsValidationError(errors)
    return result
