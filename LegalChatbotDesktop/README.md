# LegalChatbotDesktop

Native Windows desktop shell for the existing Python legal chatbot. This project is separate from the Python backend and only starts it as a child process, waits for `/health`, then displays the existing web frontend in WebView2.

## Requirements

- Windows
- .NET 8 SDK
- Microsoft Edge WebView2 Runtime

The project uses one NuGet dependency: `Microsoft.Web.WebView2`.

## Configure the backend

Edit `appsettings.json`:

```json
{
  "Backend": {
    "PythonExecutablePath": "C:\\Path\\To\\Your\\PythonProject\\.venv\\Scripts\\python.exe",
    "BackendWorkingDirectory": "C:\\Path\\To\\Your\\PythonProject",
    "Arguments": ["-m", "uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", "8000"],
    "Host": "127.0.0.1",
    "Port": 8000,
    "HealthPath": "/health",
    "FrontendUrl": "http://127.0.0.1:8000/"
  }
}
```

Use the real Python executable and backend project directory for your machine. The arguments are passed directly to `python.exe`; no shell is used.

## Build and run

From this folder:

```powershell
dotnet restore
dotnet build
dotnet run
```

On startup, the app:

1. Checks whether `127.0.0.1:8000` is already occupied.
2. Starts the configured Python command hidden with stdout and stderr redirected.
3. Polls `http://127.0.0.1:8000/health` every 500 ms for up to 30 seconds.
4. Opens `http://127.0.0.1:8000/` in WebView2 once the backend is healthy.

Backend logs are written under the configured `LogDirectory` value, defaulting to `logs` next to the built executable.

## Build the updated Windows package

From the repository root:

```powershell
powershell -NoProfile -File scripts\build_desktop.ps1
```

This publishes a self-contained Windows x64 shell, includes the current backend
configuration and installation/username guides, records the shared backend
revision in `backend-version.json`, and refreshes
`LegalChatbotDesktop/dist/LegalChatbotDesktop-win-x64.zip`.

The package uses the current Python backend and frontend from the configured
`BackendWorkingDirectory`; it does not embed an independent backend snapshot.
The 3B model-selection fix and institutional usernames therefore apply to both
the browser and desktop app. Follow `INSTALL_ON_OTHER_PC.md` when updating a
separate PC, including its own backend checkout and username migration.
