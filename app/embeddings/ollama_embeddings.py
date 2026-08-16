"""Create embeddings for prepared chunks."""


def create_chunk_embeddings(chunks: list[dict]) -> list[list[float]]:
    """Create embeddings for Chroma-ready chunks."""

    from app.build_index import create_embeddings

    return create_embeddings(chunks)
