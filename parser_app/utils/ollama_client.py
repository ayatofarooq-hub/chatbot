"""Local-only Ollama client for parser model calls."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS


class LocalOllamaClient:
    """Call a local Ollama server without exposing chatbot behavior."""

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = OLLAMA_MODEL,
        timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._validate_local_host()

    def generate_json(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 2048,
            },
        }
        request = Request(
            f"{self.host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))

        model_response = body.get("response")
        if not isinstance(model_response, str):
            raise ValueError("Ollama response did not contain a string response")
        return model_response

    def _validate_local_host(self) -> None:
        parsed = urlparse(self.host)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama host must use http or https")

        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Parser app may connect only to a local Ollama server")
