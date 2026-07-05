"""Display the offline chatbot configuration."""

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
        if engine is not None:
            engine.dispose()

    print(
        f"Offline source: database '{database_name}' as '{database_user}'"
    )
    print(f"Chroma folder: {CHROMA_FOLDER}")
    print(f"Chat model: {CHAT_MODEL}")
    print(f"Embedding model: {EMBEDDING_MODEL}")


if __name__ == "__main__":
    main()
