@echo off
REM Rin AI Secretary - Stop Script

REM Method 1: Kill by PID file (headless mode)
if exist "C:\Users\user\Desktop\AI-secretary\data\server.pid" (
    echo Stopping via PID file...
    for /f "tokens=1" %%p in (C:\Users\user\Desktop\AI-secretary\data\server.pid) do (
        taskkill /PID %%p /T /F 2>NUL
    )
    del "C:\Users\user\Desktop\AI-secretary\data\server.pid" 2>NUL
)

REM Method 2: Kill by window title (manual mode)
taskkill /FI "WINDOWTITLE eq rin-server" /T /F 2>NUL
taskkill /FI "WINDOWTITLE eq rin-tunnel" /T /F 2>NUL

REM Method 3: Kill by port 8000 (fallback)
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| find ":8000" ^| find "LISTENING"') do (
    taskkill /PID %%a /F 2>NUL
)

echo Rin server and tunnel stopped.
