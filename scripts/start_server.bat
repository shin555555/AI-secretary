@echo off
REM Rin AI Secretary - Server Start Script (manual use)

cd /d C:\Users\user\Desktop\AI-secretary

REM Check if already running on port 8000
netstat -aon 2>NUL | find ":8000" | find "LISTENING" >NUL 2>&1
if %ERRORLEVEL%==0 (
    echo Server is already running on port 8000.
    exit /b 0
)

echo Starting Rin server...

REM Start uvicorn server (minimized window)
start "rin-server" /MIN cmd /c "C:\Users\user\Desktop\AI-secretary\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Waiting for server to start...
timeout /t 5 /nobreak >NUL

echo Starting Cloudflare Tunnel + LINE Webhook auto-update...

REM Start tunnel with auto webhook update (minimized window)
start "rin-tunnel" /MIN cmd /c "C:\Users\user\Desktop\AI-secretary\.venv\Scripts\python.exe C:\Users\user\Desktop\AI-secretary\scripts\start_tunnel.py"

echo.
echo === Rin server and tunnel started ===
echo Webhook URL will be updated automatically.
