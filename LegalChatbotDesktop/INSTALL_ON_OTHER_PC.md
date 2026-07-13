# Install Legal Chatbot Desktop On Another PC

This package contains the Windows desktop shell only. It opens the existing Python chatbot backend inside a native Windows app.

## Required On The Other PC

- The full Python chatbot backend folder
- Python and the backend virtual environment
- PostgreSQL with the legal database restored
- Ollama and the required model
- Microsoft Edge WebView2 Runtime

The desktop app is self-contained for .NET, so the other PC does not need the .NET SDK.

## Basic Setup

1. Copy the Python backend folder to the other PC.
2. Create the backend virtual environment:

```powershell
cd C:\Path\To\chatbot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Configure `.env` with that PC's database connection:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DB_NAME
```

4. Restore the PostgreSQL database.
5. Install Ollama and pull the required model:

```powershell
ollama pull qwen2.5:7b
```

6. Test the backend:

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

7. Edit `appsettings.json` next to `LegalChatbotDesktop.exe`:

```json
"PythonExecutablePath": "C:\\Path\\To\\chatbot\\.venv\\Scripts\\python.exe",
"BackendWorkingDirectory": "C:\\Path\\To\\chatbot"
```

8. Run `LegalChatbotDesktop.exe`.

The app starts the backend if needed, or attaches to an already-running healthy backend on port `8000`.
