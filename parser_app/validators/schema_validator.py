"""Validation for exported standard Iraqi legal JSON objects."""

from __future__ import annotations

from typing import Any

from models.standard_schema import (
    STANDARD_SCHEMA_VERSION,
    STANDARD_TOP_LEVEL_KEYS,
    find_banned_keys,
)
from validators.validation_engine import ValidationEngine


class StandardSchemaValidator:
    """Validate the exported legal document representation."""

    def __init__(self) -> None:
        self.validation_engine = ValidationEngine()

    def validate_dict(self, document: dict[str, Any]) -> dict[str, Any]:
        return self.validation_engine.validate_dict(document)
