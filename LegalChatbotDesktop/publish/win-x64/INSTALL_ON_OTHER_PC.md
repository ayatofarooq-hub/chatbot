# Install Legal Chatbot Desktop On Another PC

This package contains the Windows desktop shell only. It opens the existing Python chatbot backend inside a native Windows app.

## 1. Copy The Required Files

Copy these to the other PC:

- This extracted desktop app folder
- The full Python chatbot backend folder
- Any database backup or PostgreSQL data needed by the backend

The desktop app does not contain the legal database, Python packages, Ollama model, or PostgreSQL server.

## 2. Install Required Software

Install these on the other PC:

- Python 3.11 or the Python version used by the backend
- PostgreSQL
- Ollama
- Microsoft Edge WebView2 Runtime

The desktop app is self-contained for .NET, so the other PC does not need the .NET SDK.

## 3. Set Up The Python Backend

Open PowerShell in the copied Python backend folder:

```powershell
cd C:\Path\To\chatbot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create or update `.env` with the PostgreSQL connection string for that PC:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DB_NAME
```

Restore or create the PostgreSQL database before running the app.

## 4. Install And Start The Ollama Model

Install Ollama, then pull the model used by the backend. For example:

```powershell
ollama pull qwen2.5:7b
```

If Ollama is not already running, start it:

```powershell
ollama serve
```

Do not start a second Ollama server if port `11434` is already in use.

## 5. Test The Backend First

From the Python backend folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Then open this in a browser:

```text
http://127.0.0.1:8000/health
```

It should show:

```json
{"status":"ok"}
```

## 6. Configure The Desktop App

In the desktop app folder, edit `appsettings.json`:

```json
{
  "Backend": {
    "PythonExecutablePath": "C:\\Path\\To\\chatbot\\.venv\\Scripts\\python.exe",
    "BackendWorkingDirectory": "C:\\Path\\To\\chatbot"
  }
}
```

Keep the default arguments if the backend still runs with:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

## 7. Run The Desktop App

Double-click:

```text
LegalChatbotDesktop.exe
```

The app will:

1. Start the Python backend if port `8000` is free.
2. Use the existing backend if `http://127.0.0.1:8000/health` is already OK.
3. Open the chatbot interface in the desktop window.

## Troubleshooting

If the app says port `8000` is already in use, check:

```text
http://127.0.0.1:8000/health
```

If it returns `{"status":"ok"}`, restart the desktop app.

If it does not return OK, close the process using port `8000` or change the port in `appsettings.json`.

Backend logs are written in the desktop app's `logs` folder.
