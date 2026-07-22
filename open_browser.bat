@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Move to this script's folder so paths work from any launch location.
cd /d "%~dp0"

set "SERVER_HOST=127.0.0.1"
set "SERVER_PORT=8000"
set "SERVER_URL=http://localhost:8000"
set "MAX_ATTEMPTS=30"

echo ============================================================
echo Iraqi Legal Assistant - Open Browser
echo URL: %SERVER_URL%
echo ============================================================
echo.

REM Wait until the server port accepts TCP connections.
echo [INFO] Waiting for server on %SERVER_HOST%:%SERVER_PORT%...
for /L %%A in (1,1,%MAX_ATTEMPTS%) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object Net.Sockets.TcpClient; try { $client.Connect('%SERVER_HOST%', %SERVER_PORT%); $client.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
    if "!errorlevel!"=="0" (
        echo [OK] Server is reachable.
        echo [INFO] Opening default browser...
        start "" "%SERVER_URL%"
        if not "!errorlevel!"=="0" (
            echo [ERROR] Failed to open browser.
            pause
            exit /b 1
        )
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)

echo [ERROR] Server did not respond on %SERVER_HOST%:%SERVER_PORT% after %MAX_ATTEMPTS% seconds.
echo [INFO] Start the server with run_server.bat, then run this script again.
pause
exit /b 1
