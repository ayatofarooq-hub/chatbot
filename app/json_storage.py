"""Small JSON-file persistence helpers with atomic writes."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

_LOCK = threading.RLock()


def read_json(path: Path, default: T) -> Any:
    """Read JSON from ``path`` or return ``default`` when it does not exist."""

    with _LOCK:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically so interrupted writes do not corrupt data."""

    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, path)


def update_json(path: Path, default: T, updater: Callable[[Any], Any]) -> Any:
    """Read, update, and atomically write one JSON document."""

    with _LOCK:
        payload = read_json(path, default)
        updated = updater(payload)
        write_json(path, updated)
        return updated
