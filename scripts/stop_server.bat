@echo off
REM Rin AI Secretary - Stop Script

taskkill /FI "WINDOWTITLE eq rin-server" /T /F 2>NUL
taskkill /FI "WINDOWTITLE eq rin-tunnel" /T /F 2>NUL

echo Rin server and tunnel stopped.
pause
