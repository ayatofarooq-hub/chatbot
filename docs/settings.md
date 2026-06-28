# Settings module

## Installation

The settings schema is explicit and is never applied during API startup.

```powershell
.\.venv\Scripts\python.exe scripts\apply_migration.py
.\.venv\Scripts\python.exe scripts\create_admin.py
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Use HTTPS when the server is reachable from another machine. Administrator
sessions use an HttpOnly, SameSite=Strict cookie; its `Secure` flag is enabled
when the request is served over HTTPS. Do not expose Ollama or PostgreSQL to
untrusted networks.

The migration creates only application-owned tables. It reads distinct values
from `public.iraqi_laws.classification` to seed display metadata and does not
change the legal table schema. Classification reassignment updates linked legal
records and soft-deletes the old classification in one transaction.

## Runtime effects

Model and retrieval settings are loaded for subsequent requests. Embedding
model and chunk settings require an explicit index rebuild. The rebuild uses
the existing PostgreSQL-to-chunks-to-citation-registry-to-Chroma pipeline.
Changing application settings never mutates Chroma directly.

JSON export/import contains application settings only. It does not contain
administrator password hashes, sessions, legal records, Chroma data, or
database credentials.

## Not configured

- The existing browser uploader simulates progress and has no upload API.
  Upload settings are persisted but disabled in the Settings UI until a real
  endpoint can enforce them server-side.
- No fine-tuning pipeline exists, so the section is disabled and no run or
  progress endpoints are exposed.
- Database-native backup/restore and automatic backup scheduling are not
  configured. The related endpoints return HTTP 501.
- Browser notification preferences are stored, but no email or desktop
  delivery mechanism is presented.
