"""PostgreSQL connection helpers for the existing Iraqi laws database."""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, RowMapping


load_dotenv()


def database_url(required: bool = True) -> str | None:
    """Return the configured SQLAlchemy PostgreSQL URL."""

    value = os.getenv("DATABASE_URL", "").strip()
    if not value and required:
        raise RuntimeError(
            "DATABASE_URL is not configured. Add it to .env or the environment."
        )
    return value or None


def create_database_engine(url: str | None = None) -> Engine:
    """Create a pooled SQLAlchemy engine with connection health checks."""

    return create_engine(
        url or database_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def iter_iraqi_laws(engine: Engine) -> Iterator[RowMapping]:
    """Yield rows from the existing public.iraqi_laws table."""

    query = text(
        """
        SELECT
            id,
            classification,
            law_number,
            law_year,
            article_number,
            law_name,
            summary
        FROM public.iraqi_laws
        ORDER BY id
        """
    )
    with engine.connect() as connection:
        yield from connection.execute(query).mappings()


def connection_identity(engine: Engine) -> tuple[str, str]:
    """Return the connected database and role names."""

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()
    return str(row[0]), str(row[1])


def main() -> None:
    """Check the configured database connection."""

    engine = create_database_engine()
    try:
        name, user = connection_identity(engine)
        print(f"Connected to PostgreSQL database '{name}' as '{user}'.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
