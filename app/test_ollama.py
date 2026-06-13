"""Diagnostic script for testing the configured local Ollama models."""

import sys

import httpx
import ollama

try:
    from .config import (
        CHAT_MODEL,
        EMBEDDING_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    from .ollama_client import client as ollama_client
except ImportError:
    # Support direct execution with: python app/test_ollama.py
    from config import (
        CHAT_MODEL,
        EMBEDDING_MODEL,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )
    from ollama_client import client as ollama_client


CHAT_PROMPT = "أجب بجملة قصيرة: ما أهمية القانون في تنظيم المجتمع؟"
EMBEDDING_TEXT = "يضمن القانون حماية الحقوق وتنظيم الالتزامات القانونية."


def main() -> None:
    """Test one chat request and one Arabic embedding request."""

    try:
        chat_response = ollama_client.chat(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": CHAT_PROMPT,
                }
            ],
            keep_alive=OLLAMA_KEEP_ALIVE,
        )

        embedding_response = ollama_client.embed(
            model=EMBEDDING_MODEL,
            input=EMBEDDING_TEXT,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
    except ConnectionError:
        print("Could not connect to Ollama. Make sure the Ollama service is running.")
        sys.exit(1)
    except httpx.TimeoutException:
        print(
            "Ollama request timed out after "
            f"{OLLAMA_REQUEST_TIMEOUT_SECONDS} seconds."
        )
        sys.exit(1)
    except ollama.ResponseError as error:
        print(f"Ollama request failed: {error}")
        sys.exit(1)

    chat_text = chat_response["message"]["content"]
    embedding_length = len(embedding_response["embeddings"][0])

    print("Chat response:")
    print(chat_text)
    print()
    print(f"Embedding vector length: {embedding_length}")


if __name__ == "__main__":
    main()
