# LegalChatbotDesktop Other PC Setup

This folder contains the published Windows desktop shell.

## What is included

- `LegalChatbotDesktop.exe`
- Self-contained .NET 8 desktop runtime files
- WebView2 integration package files
- `appsettings.json`

## What the other PC still needs

- The Python chatbot backend project copied to that PC
- A working Python environment for the backend
- The backend database and any local services it depends on
- Microsoft Edge WebView2 Runtime installed

## Configure on the other PC

Edit `appsettings.json` next to `LegalChatbotDesktop.exe` and update:

```json
"PythonExecutablePath": "C:\\Path\\To\\PythonProject\\.venv\\Scripts\\python.exe",
"BackendWorkingDirectory": "C:\\Path\\To\\PythonProject"
```

Keep the default arguments if the backend is still launched with:

```powershell
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Then run:

```powershell
.\LegalChatbotDesktop.exe
```
