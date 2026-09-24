@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==============================================
echo   RAG Call Center Agent - Local Launcher
echo ==============================================
echo.

REM --- 1) Start PostgreSQL only if you're using it (safe to skip for SQLite) ---
echo [1/4] Checking for a PostgreSQL service (only needed if DATABASE_URL uses Postgres)...
powershell -NoProfile -Command ^
  "$s = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue;" ^
  "if ($s) { if ($s.Status -ne 'Running') { Start-Service $s.Name }; Write-Host '  PostgreSQL service:' $s.Name '->' (Get-Service $s.Name).Status }" ^
  "else { Write-Host '  No PostgreSQL service found - fine if you are using the default SQLite database.' }"
echo.

REM --- 2) Start ngrok in its own window -----------------------------------
echo [2/4] Starting ngrok tunnel on port 8000...
start "ngrok" cmd /k ngrok http 8000
echo   Waiting for ngrok to come up...
timeout /t 5 /nobreak >nul
echo.

REM --- 3) Grab the public URL and write it into .env ----------------------
echo [3/4] Fetching the public ngrok URL...
set NGROK_URL=
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "try { (Invoke-RestMethod http://127.0.0.1:4040/api/tunnels).tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -First 1 -ExpandProperty public_url } catch { '' }"`) do set NGROK_URL=%%A

if "!NGROK_URL!"=="" (
    echo   WARNING: could not read the ngrok URL automatically.
    echo   Open http://127.0.0.1:4040 in a browser, copy the https URL,
    echo   and paste it into .env as PUBLIC_BASE_URL manually.
) else (
    echo   ngrok URL: !NGROK_URL!
    if exist ".env" (
        powershell -NoProfile -Command ^
          "(Get-Content .env) -replace '^PUBLIC_BASE_URL=.*', 'PUBLIC_BASE_URL=!NGROK_URL!' | Set-Content .env"
        echo   .env updated with the new PUBLIC_BASE_URL
    ) else (
        echo   WARNING: .env not found next to this script - skipped auto-update.
    )
)
echo.

REM --- 4) Start the app server in its own window ---------------------------
echo [4/4] Starting the FastAPI server...
start "RAG Call Center Agent - Server" cmd /k uvicorn app.main:app --reload
echo.

echo ==============================================
echo   All set. Two windows just opened: ngrok + the app server.
echo   Customer chat : http://localhost:8000
echo   Admin dashboard: http://localhost:8000/admin.html
echo   Close those two windows whenever you want to stop everything.
echo ==============================================
pause
