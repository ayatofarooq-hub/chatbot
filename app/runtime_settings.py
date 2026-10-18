"""Resolve current JSON-backed settings with safe code defaults."""

from __future__ import annotations

from copy import deepcopy

from .model_selection import hardware_profile
from .settings_schema import DEFAULTS
from .settings_store import get_settings


def runtime_settings() -> dict:
    """Read current settings for each request with defaults as fallback."""

    try:
        settings = get_settings()
    except Exception:
        settings = deepcopy(DEFAULTS)
    if settings["model"].get("auto_select_model", True):
        settings["model"]["chat_model"] = hardware_profile()["recommended_model"]
    return settings
