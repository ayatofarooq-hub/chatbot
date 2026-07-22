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
