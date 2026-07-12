"""Central configuration for project paths and local model names."""

from pathlib import Path


# The project root is the directory that contains the ``app`` and ``data``
# folders. Building paths from this location keeps them valid regardless of
# the directory from which Python is started.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The legal knowledge source is a local JSON repository plus generated embeddings.
CHROMA_FOLDER = PROJECT_ROOT / "data" / "chroma"
CITATION_REGISTRY_FILE = PROJECT_ROOT / "data" / "citation_registry.json"

# Models that will be used by the future RAG chatbot.
CHAT_MODEL = "qwen2.5:3b"
EMBEDDING_MODEL = "bge-m3"

# Local models can take time to load on CPU-only machines, but requests should
# still fail instead of waiting forever when Ollama becomes unresponsive.
OLLAMA_REQUEST_TIMEOUT_SECONDS = 300
OLLAMA_KEEP_ALIVE = "10m"
# Query embeddings are only needed before chat generation. Unload the
# embedding model afterward so low-VRAM GPUs can offload more chat layers.
EMBEDDING_QUERY_KEEP_ALIVE = 0
# A 7B model runs mostly on CPU on lower-VRAM laptops. Keep answers focused so
# generation completes in a practical amount of time.
CHAT_MAX_TOKENS = 400

# Print retrieved chunks before answer generation when troubleshooting RAG.
retrieved_context_debug = False


def create_data_directories() -> None:
    """Create the local data directories if they do not already exist."""

    CHROMA_FOLDER.mkdir(parents=True, exist_ok=True)
