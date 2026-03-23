# Rin AI Secretary - Task Scheduler Setup
# Run as Administrator: powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Rin AI Secretary - Scheduler Setup ===" -ForegroundColor Cyan
Write-Host ""

$pythonExe = "C:\Users\user\Desktop\AI-secretary\.venv\Scripts\pythonw.exe"
$startupScript = "C:\Users\user\Desktop\AI-secretary\scripts\startup.py"
$workingDir = "C:\Users\user\Desktop\AI-secretary"

# --- 1. Weekday 7:30 Wake + Start ---
$taskName = "RinAISecretary-WakeAndStart"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Removing existing task '$taskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $startupScript -WorkingDirectory $workingDir

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 07:30

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Rin AI Secretary: Wake from sleep and start server at 7:30 on weekdays"

Write-Host "[OK] Task '$taskName' registered (Weekdays 7:30, WakeToRun)" -ForegroundColor Green

# --- 2. Start on Logon ---
$taskNameLogon = "RinAISecretary-OnLogon"
$existingLogon = Get-ScheduledTask -TaskName $taskNameLogon -ErrorAction SilentlyContinue

if ($existingLogon) {
    Write-Host "Removing existing task '$taskNameLogon'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskNameLogon -Confirm:$false
}

$actionLogon = New-ScheduledTaskAction -Execute $pythonExe -Argument $startupScript -WorkingDirectory $workingDir

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn

$principalLogon = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

$settingsLogon = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskNameLogon `
    -Action $actionLogon `
    -Trigger $triggerLogon `
    -Settings $settingsLogon `
    -Principal $principalLogon `
    -Description "Rin AI Secretary: Start server on user logon"

Write-Host "[OK] Task '$taskNameLogon' registered (Start on logon)" -ForegroundColor Green

# --- 3. Sleep at 0:00 ---
$taskNameSleep = "RinAISecretary-SleepAt0"
$existingSleep = Get-ScheduledTask -TaskName $taskNameSleep -ErrorAction SilentlyContinue

if ($existingSleep) {
    Write-Host "Removing existing task '$taskNameSleep'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskNameSleep -Confirm:$false
}

$sleepScript = "C:\Users\user\Desktop\AI-secretary\scripts\sleep_server.bat"
$actionSleep = New-ScheduledTaskAction -Execute $sleepScript -WorkingDirectory $workingDir

$triggerSleep = New-ScheduledTaskTrigger -Daily -At 00:00

$principalSleep = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

$settingsSleep = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskNameSleep `
    -Action $actionSleep `
    -Trigger $triggerSleep `
    -Settings $settingsSleep `
    -Principal $principalSleep `
    -Description "Rin AI Secretary: Stop server and sleep PC at midnight"

Write-Host "[OK] Task '$taskNameSleep' registered (Daily 0:00, stop + sleep)" -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "1. Weekday 7:30 - Wake from sleep + start server" -ForegroundColor White
Write-Host "2. On logon - Auto start server" -ForegroundColor White
Write-Host "3. Daily 0:00 - Stop server + sleep PC" -ForegroundColor White
Write-Host ""
Write-Host "Verify: taskschd.msc -> search 'RinAISecretary'" -ForegroundColor Gray
Write-Host "Manual start: scripts\start_server.bat" -ForegroundColor Gray
Write-Host "Manual stop:  scripts\stop_server.bat" -ForegroundColor Gray
