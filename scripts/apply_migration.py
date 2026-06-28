"""Apply an explicit SQL migration without requiring the psql executable."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import create_database_engine


def apply_migration(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Migration file was not found: {resolved}")

    sql = resolved.read_text(encoding="utf-8")
    engine = create_database_engine()
    try:
        # The migration owns its BEGIN/COMMIT boundary and is idempotent.
        with engine.connect() as connection:
            connection.exec_driver_sql(sql)
        print(f"Applied migration: {resolved.relative_to(PROJECT_ROOT)}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "migration",
        nargs="?",
        default=str(PROJECT_ROOT / "migrations" / "001_settings.sql"),
        type=Path,
    )
    arguments = parser.parse_args()
    apply_migration(arguments.migration)


if __name__ == "__main__":
    main()
