# Install Legal Chatbot Desktop On Another PC

This package contains the Windows desktop shell only. It opens the existing
Python chatbot backend inside a native Windows app.

## Required On The Other PC

- The current Python chatbot backend folder, including its legal sources, index,
  citation registry, frontend, and application settings
- Python and the backend virtual environment
- Ollama and the required models
- Microsoft Edge WebView2 Runtime

The desktop app is self-contained for .NET, so the other PC does not need the
.NET SDK.

## Basic Setup

1. Copy the Python backend folder to the other PC.
2. Create the backend virtual environment:

```powershell
cd C:\Path\To\chatbot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Transfer the existing legal data and its matching generated index/registry,
   or configure the durable PostgreSQL legal source using the backend README
   and rebuild through the supported ingestion command:

```powershell
.\.venv\Scripts\python.exe -m app.build_index
```

4. Install Ollama and pull the required models:

```powershell
ollama pull qwen2.5:3b
ollama pull bge-m3
```

5. Test the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

6. Edit `appsettings.json` next to `LegalChatbotDesktop.exe`:

```json
"PythonExecutablePath": "C:\\Path\\To\\chatbot\\.venv\\Scripts\\python.exe",
"BackendWorkingDirectory": "C:\\Path\\To\\chatbot"
```

7. Run `LegalChatbotDesktop.exe`.

The app starts the backend if needed, or attaches to an already-running healthy
backend on port `8000`.

## Updating An Existing Installation

The desktop executable does not contain a second Python backend. It launches
`app.api:app` from `BackendWorkingDirectory` in `appsettings.json`. Update that
backend checkout to the latest project version and keep its Python environment,
local data, settings, and model files. Do not replace an existing installation's
`data/metadata.json` with another PC's account/session data.

After updating an older checkout, run the username migration once:

```powershell
.\.venv\Scripts\python.exe scripts\rename_ministry_usernames.py
```

The ministry login names include `MOH`, `MOC`, and `MOCH`; see the packaged
`ministry-usernames.md` for the full list. Passwords and permissions stay the same.

Keep `qwen2.5:3b` selected and automatic model selection disabled to retain the
verified answer behavior. Automatic selection is opt-in and may choose a smaller
model with different accuracy.

Stop and restart the backend after updating it. Closing a desktop window does
not stop a server that was already running before the window opened. On the
development PC, the desktop app and browser use the same backend and data.

`backend-version.json` in the desktop package records the backend revision and
working directory used when the package was built. It describes that build;
the shared backend can subsequently be updated independently.
