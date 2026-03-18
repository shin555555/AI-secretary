# Rin AI Secretary - Task Scheduler Setup
# Run as Administrator

$ErrorActionPreference = "Stop"

Write-Host "=== Rin AI Secretary - Scheduler Setup ===" -ForegroundColor Cyan

# --- 1. Weekday 7:30 Wake + Start ---
$taskName = "RinAISecretary-WakeAndStart"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Removing existing task '$taskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "C:\Users\user\Desktop\AI-secretary\scripts\start_server.bat" -WorkingDirectory "C:\Users\user\Desktop\AI-secretary"

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 07:30

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Rin AI Secretary: Wake from sleep and start server at 7:30 on weekdays"

Write-Host "[OK] Task '$taskName' registered (Weekdays 7:30, WakeToRun enabled)" -ForegroundColor Green

# --- 2. Start on Logon ---
$taskNameLogon = "RinAISecretary-OnLogon"
$existingLogon = Get-ScheduledTask -TaskName $taskNameLogon -ErrorAction SilentlyContinue

if ($existingLogon) {
    Write-Host "Removing existing task '$taskNameLogon'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskNameLogon -Confirm:$false
}

$actionLogon = New-ScheduledTaskAction -Execute "C:\Users\user\Desktop\AI-secretary\scripts\start_server.bat" -WorkingDirectory "C:\Users\user\Desktop\AI-secretary"

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn

$settingsLogon = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $taskNameLogon -Action $actionLogon -Trigger $triggerLogon -Settings $settingsLogon -Description "Rin AI Secretary: Start server on user logon"

Write-Host "[OK] Task '$taskNameLogon' registered (Start on logon)" -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "1. Weekday 7:30 - Wake from sleep + start server" -ForegroundColor White
Write-Host "2. On logon - Auto start server" -ForegroundColor White
Write-Host ""
Write-Host "Verify: taskschd.msc -> search 'RinAISecretary'" -ForegroundColor Gray
Write-Host "Manual start: scripts\start_server.bat" -ForegroundColor Gray
Write-Host "Manual stop:  scripts\stop_server.bat" -ForegroundColor Gray
