@echo off
REM Rin AI Secretary - Stop Server and Sleep PC
REM タスクスケジューラから毎日0:00に実行される

cd /d C:\Users\user\Desktop\AI-secretary

echo [%date% %time%] Stopping server and entering sleep... >> data\logs\startup.log

REM サーバー停止
call scripts\stop_server.bat

REM 3秒待ってからスリープ
timeout /t 3 /nobreak >NUL

REM PCをスリープ状態にする
rundll32.exe powrprof.dll,SetSuspendState 0,1,0
