@echo off
setlocal EnableExtensions

REM Move to this script's folder so paths work from any launch location.
cd /d "%~dp0"

echo ============================================================
echo Iraqi Legal Assistant - Run Server
echo Framework: FastAPI/Starlette
echo Entry point: app.api:app
echo URL: http://localhost:8000
echo ============================================================
echo.

REM Prefer the existing repo virtual environment, then fall back to venv.
set "VENV_DIR="
if exist "%~dp0.venv\Scripts\python.exe" if exist "%~dp0.venv\Scripts\activate.bat" set "VENV_DIR=%~dp0.venv"
if not defined VENV_DIR if exist "%~dp0venv\Scripts\python.exe" if exist "%~dp0venv\Scripts\activate.bat" set "VENV_DIR=%~dp0venv"

REM Ensure a complete virtual environment exists.
if not defined VENV_DIR (
    echo [ERROR] Virtual environment not found.
    echo [INFO] Run setup.bat first.
    pause
    exit /b 1
)

REM Activate the virtual environment.
echo [INFO] Activating virtual environment: %VENV_DIR%
call "%VENV_DIR%\Scripts\activate.bat"
if not "%errorlevel%"=="0" (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Avoid WinError 10048 when this project is already serving on port 8000.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } } catch {}; exit 1" >nul 2>&1
if "%errorlevel%"=="0" (
    echo [INFO] The Iraqi Legal Assistant is already running.
    echo [INFO] Open http://localhost:8000 and press CTRL+F5 to refresh.
    exit /b 0
)

set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano -p TCP ^| findstr ":8000" ^| findstr "LISTENING"') do set "PORT_PID=%%P"
if defined PORT_PID (
    echo [ERROR] Port 8000 is being used by another application ^(PID %PORT_PID%^).
    echo [INFO] Stop that application or start this server on a different port.
    pause
    exit /b 1
)

REM Verify uvicorn is installed before launching.
python -m uvicorn --version >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [ERROR] uvicorn is not installed in the virtual environment.
    echo [INFO] Run setup.bat to install requirements.
    pause
    exit /b 1
)

echo [INFO] Starting FastAPI server on http://localhost:8000
echo [INFO] Press CTRL+C to stop the server.
echo.

REM Start the existing project server and keep this window open for logs.
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
set "SERVER_EXIT=%errorlevel%"

echo.
if not "%SERVER_EXIT%"=="0" (
    echo [ERROR] Server exited with code %SERVER_EXIT%.
) else (
    echo [INFO] Server stopped.
)
pause
exit /b %SERVER_EXIT%
