@echo off
REM Rin AI Secretary - Server Start Script

cd /d C:\Users\user\Desktop\AI-secretary

REM Check if already running
tasklist /FI "WINDOWTITLE eq rin-server" 2>NUL | find /I "python" >NUL
if %ERRORLEVEL%==0 (
    echo Server is already running.
    pause
    exit /b 0
)

echo Starting Rin server...

REM Start uvicorn server
start "rin-server" /MIN cmd /c "C:\Users\user\Desktop\AI-secretary\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Waiting for server to start...
timeout /t 5 /nobreak >NUL

echo Starting Cloudflare Tunnel + LINE Webhook auto-update...

REM Start tunnel with auto webhook update
start "rin-tunnel" /MIN cmd /c "C:\Users\user\Desktop\AI-secretary\.venv\Scripts\python.exe C:\Users\user\Desktop\AI-secretary\scripts\start_tunnel.py"

echo.
echo === Rin server and tunnel started ===
echo Webhook URL will be updated automatically.
pause
