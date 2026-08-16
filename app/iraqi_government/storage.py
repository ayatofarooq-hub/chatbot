"""JSON storage for Iraqi government preprocessing output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_standard_json(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Save standardized JSON as UTF-8 and return the written path."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
