"""Resolve current JSON-backed settings with safe code defaults."""

from __future__ import annotations

from copy import deepcopy

from .settings_schema import DEFAULTS
from .settings_store import get_settings


def runtime_settings() -> dict:
    """Read current settings for each request with defaults as fallback."""

    try:
        return get_settings()
    except Exception:
        return deepcopy(DEFAULTS)
