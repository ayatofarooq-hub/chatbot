"""Shared Ollama client configuration for local model requests."""

import ollama

try:
    from .config import OLLAMA_REQUEST_TIMEOUT_SECONDS
except ImportError:
    from config import OLLAMA_REQUEST_TIMEOUT_SECONDS


client = ollama.Client(timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS)
