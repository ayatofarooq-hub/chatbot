# Frontend Migration

## Decision

The PDF design requires a fixed RTL application shell with four independently
scrolling regions, precise responsive breakpoints, persistent browser state,
and direct control over message, toolbar, and composer placement.

Streamlit remains useful as an internal diagnostic client, but it is not the
primary frontend because:

- its generated DOM and `data-testid` selectors are implementation details;
- interactions trigger Python reruns rather than local UI state updates;
- fixed and independently scrolling panels are difficult to maintain;
- responsive column ordering and mobile navigation are constrained;
- the chat composer cannot be positioned precisely within a custom grid;
- browser history and transitions require workarounds.

## Target Architecture

```text
Browser
  |
  | GET /, /assets/*
  | POST /ask
  v
Starlette (app/api.py)
  |
  +-- Existing RAG, citation, Ollama, Chroma, and document-store modules
```

The browser frontend uses plain HTML, CSS, and JavaScript. It introduces no
Node.js build requirement and is served by the existing Starlette process.

## Compatibility

Existing API routes and response payloads remain unchanged:

- `GET /health`
- `POST /ask`
- `GET /documents`
- `POST /documents`
- `PUT /documents/{filename}`
- `DELETE /documents/{filename}`

The Streamlit interface remains available through `app/ui.py` as a fallback.

## Rollback

The migration can be rolled back operationally by launching Streamlit instead
of the Starlette browser frontend. No backend or database migration is needed.
