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

## Typography Migration

All browser UI typography now uses `IBM Plex Sans Arabic` through a single CSS
token:

```css
:root {
  --font-primary: "IBM Plex Sans Arabic", sans-serif;
}
```

The token is applied globally to the document and inherited by buttons, inputs,
forms, cards, dialogs/toasts, and dynamic components. Font weights are limited
to the requested IBM Plex Sans Arabic scale: 300, 400, 500, 600, and 700. The
Streamlit fallback design system uses the same font token.

## Decision Upload Redesign

The `قرار جديد` page now uses a document-management uploader instead of the old
single attachment field.

- Supported files: PDF, DOC, DOCX.
- Maximum files per decision: 3.
- Maximum file size: 100 MB per file.
- Validation runs before upload and reports all rejected files.
- Uploads run concurrently and additional files can be added while other files
  are still uploading.
- Completed files show name, size, upload date/time, status, preview, download,
  delete, reorder, and more-actions controls.
- The current-files section displays `عدد الملفات: n / 3`.
- The statistics panel displays total uploaded size, maximum file size, current
  count, and remaining capacity.

The current backend does not expose binary file persistence. Upload progress is
therefore simulated in the browser and file actions use local object URLs until
a binary upload endpoint is added.

## Upload Component Layout

The static frontend keeps component separation through ES modules under:

```text
frontend/components/upload/
  UploadDropzone.js
  UploadProgressCard.js
  UploadedFileCard.js
  UploadStats.js
  FileActions.js
  useUploadManager.js
  uploadService.js
  uploadTypes.js
  uploadValidation.js
  uploadFormatters.js
```

This preserves the no-build deployment model while keeping the upload UI,
validation, rendering, and progress service isolated.

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
