"""Offline compatibility helpers for the JSON-backed legal repository."""

from __future__ import annotations

import os
from collections.abc import Iterator


def database_url(required: bool = True) -> str | None:
    """Return a placeholder value for compatibility with older modules."""

    value = os.getenv("DATABASE_URL", "").strip()
    if not value and required:
        return None
    return value or None


def create_database_engine(url: str | None = None):
    """Return None because the project now uses JSON files only."""

    return None


def iter_iraqi_laws(engine=None) -> Iterator[dict]:
    """Yield no rows because the project uses the offline JSON repository."""

    if False:
        yield {}
    return iter(())


def connection_identity(engine=None) -> tuple[str, str]:
    """Return placeholder values for compatibility."""

    return "json", "offline"


def main() -> None:
    """Report that the offline JSON repository is in use."""

    print("Offline JSON repository active.")


if __name__ == "__main__":
    main()
