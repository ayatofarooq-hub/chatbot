# Settings Module

## Installation

The settings schema is stored in `data/metadata.json`; no migration step is
required.

```powershell
.\.venv\Scripts\python.exe scripts\create_admin.py
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Use HTTPS when the server is reachable from another machine. Administrator
sessions use an HttpOnly, SameSite=Strict cookie; its `Secure` flag is enabled
when the request is served over HTTPS. Do not expose Ollama to untrusted
networks.

Classifications are stored in JSON metadata and can be edited through the
settings API. Classification reassignment updates JSON legal records when a
caller implements that workflow.

## Runtime Effects

Model and retrieval settings are loaded for subsequent requests. Embedding
model and chunk settings require an explicit index rebuild. The rebuild uses
the JSON-to-chunks-to-citation-registry-to-Chroma pipeline. Changing
application settings never mutates Chroma directly.

### Automatic local model selection

The supported chat models are `qwen2.5:1.5b`, `qwen2.5:3b`, and
`qwen2.5:7b`. With `model.auto_select_model` enabled, application startup
checks dedicated GPU memory using `nvidia-smi` first and Windows video-controller
information as a fallback. It selects 1.5B below 4 GB (and for CPU-only
systems), 3B from 4 GB, and 7B from 8 GB. Disable automatic selection in the
settings page to keep a manual model choice.

JSON export/import contains application settings only. It does not contain
administrator password hashes, sessions, legal records, or Chroma data.

## Not Configured

- No fine-tuning pipeline exists, so the section is disabled and no run or
  progress endpoints are exposed.
- JSON backup/restore is handled through settings export/import.
- Browser notification preferences are stored, but no email or desktop
  delivery mechanism is presented.
