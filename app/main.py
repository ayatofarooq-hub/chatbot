"""Display the PostgreSQL-only chatbot configuration."""

from app.config import (
    CHAT_MODEL,
    CHROMA_FOLDER,
    EMBEDDING_MODEL,
    create_data_directories,
)
from app.database import create_database_engine, connection_identity


def main() -> None:
    """Prepare local folders and display the current configuration."""

    create_data_directories()

    engine = create_database_engine()
    try:
        database_name, database_user = connection_identity(engine)
    finally:
        engine.dispose()

    print(
        f"PostgreSQL source: database '{database_name}' as '{database_user}'"
    )
    print(f"Chroma folder: {CHROMA_FOLDER}")
    print(f"Chat model: {CHAT_MODEL}")
    print(f"Embedding model: {EMBEDDING_MODEL}")


if __name__ == "__main__":
    main()
