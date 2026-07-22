@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Move to this script's folder so paths work from any launch location.
cd /d "%~dp0"c:\Users\lenovo\Downloads\2024\2024\اياد الجلسة 41\التربية تعيينات صلاح الدين.doc

echo ============================================================
echo Iraqi Legal Assistant - Windows Setup
echo Framework: FastAPI/Starlette
echo Entry point: app.api:app
echo Port: 8000
echo ============================================================
echo.

REM Prefer the existing repo virtual environment, then fall back to venv.
set "VENV_DIR="
if exist "%~dp0.venv\Scripts\python.exe" if exist "%~dp0.venv\Scripts\activate.bat" set "VENV_DIR=%~dp0.venv"
if not defined VENV_DIR if exist "%~dp0venv\Scripts\python.exe" if exist "%~dp0venv\Scripts\activate.bat" set "VENV_DIR=%~dp0venv"

REM Find an existing Python 3 installation.
set "PYTHON_CMD="
py -3 --version >nul 2>&1
if "%errorlevel%"=="0" set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if "%errorlevel%"=="0" set "PYTHON_CMD=python"
)

REM Install Python if it is missing. Prefer winget, then fall back to a per-user direct installer.
if not defined PYTHON_CMD (
    echo [WARN] Python 3 was not found.
    echo [INFO] Attempting to install Python 3.12 using winget without administrator privileges...
    winget --version >nul 2>&1
    if "%errorlevel%"=="0" (
        winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
        if not "%errorlevel%"=="0" (
            echo [WARN] winget Python install failed. Falling back to direct installer download...
        )
    ) else (
        echo [WARN] winget is not available. Falling back to direct installer download...
    )

    py -3 --version >nul 2>&1
    if "%errorlevel%"=="0" set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    set "PYTHON_INSTALLER=%TEMP%\python-3.12.8-amd64.exe"
    echo [INFO] Downloading Python installer...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '%PYTHON_INSTALLER%'"
    if not "%errorlevel%"=="0" (
        echo [ERROR] Failed to download Python installer.
        pause
        exit /b 1
    )

    echo [INFO] Installing Python silently for the current user...
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
    if not "%errorlevel%"=="0" (
        echo [ERROR] Python installer failed.
        pause
        exit /b 1
    )

    py -3 --version >nul 2>&1
    if "%errorlevel%"=="0" set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python installation could not be verified. Open a new Command Prompt and try again.
    pause
    exit /b 1
)

echo [OK] Python found:
%PYTHON_CMD% --version
if not "%errorlevel%"=="0" (
    echo [ERROR] Python command failed.
    pause
    exit /b 1
)

REM Create a virtual environment only if no complete local environment exists.
if not defined VENV_DIR (
    set "VENV_DIR=%~dp0venv"
    echo [INFO] Creating virtual environment: !VENV_DIR!
    %PYTHON_CMD% -m venv "!VENV_DIR!"
    if not "%errorlevel%"=="0" (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [OK] Virtual environment found: !VENV_DIR!
)

if not exist "!VENV_DIR!\Scripts\activate.bat" (
    echo [ERROR] Virtual environment is incomplete: !VENV_DIR!
    echo [ERROR] Missing file: !VENV_DIR!\Scripts\activate.bat
    echo [INFO] Delete the broken venv folder or use the existing .venv folder, then rerun setup.bat.
    pause
    exit /b 1
)

REM Activate the virtual environment.
echo [INFO] Activating virtual environment...
call "!VENV_DIR!\Scripts\activate.bat"
if not "%errorlevel%"=="0" (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Upgrade pip before installing project packages.
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if not "%errorlevel%"=="0" (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
)

REM Install project dependencies.
if not exist "%~dp0requirements.txt" (
    echo [ERROR] requirements.txt was not found in %~dp0
    pause
    exit /b 1
)

echo [INFO] Installing dependencies from requirements.txt...
python -m pip install -r "%~dp0requirements.txt"
if not "%errorlevel%"=="0" (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Setup completed successfully.
echo Run run_server.bat to start the FastAPI server.
echo.
pause
exit /b 0
