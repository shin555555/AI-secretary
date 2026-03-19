# Rin AI Secretary - Task Scheduler Setup
# Run as Administrator: powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Rin AI Secretary - Scheduler Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- Password prompt for "Run whether user is logged on or not" ---
Write-Host "Task Scheduler needs your Windows password to run tasks on lock screen." -ForegroundColor Yellow
$password = Read-Host "Enter Windows password for user '$env:USERNAME'" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

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
    -User $env:USERNAME `
    -Password $plainPassword `
    -RunLevel Highest `
    -Description "Rin AI Secretary: Wake from sleep and start server at 7:30 on weekdays"

Write-Host "[OK] Task '$taskName' registered (Weekdays 7:30, WakeToRun, runs on lock screen)" -ForegroundColor Green

# --- 2. Start on Logon ---
$taskNameLogon = "RinAISecretary-OnLogon"
$existingLogon = Get-ScheduledTask -TaskName $taskNameLogon -ErrorAction SilentlyContinue

if ($existingLogon) {
    Write-Host "Removing existing task '$taskNameLogon'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskNameLogon -Confirm:$false
}

$actionLogon = New-ScheduledTaskAction -Execute $pythonExe -Argument $startupScript -WorkingDirectory $workingDir

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn

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
    -User $env:USERNAME `
    -Password $plainPassword `
    -Description "Rin AI Secretary: Start server on user logon"

Write-Host "[OK] Task '$taskNameLogon' registered (Start on logon)" -ForegroundColor Green

# --- Clear password from memory ---
$plainPassword = $null
[GC]::Collect()

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "1. Weekday 7:30 - Wake from sleep + start server (runs on lock screen)" -ForegroundColor White
Write-Host "2. On logon - Auto start server" -ForegroundColor White
Write-Host ""
Write-Host "Key changes from previous version:" -ForegroundColor Gray
Write-Host "  - Uses startup.py (headless, no GUI windows)" -ForegroundColor Gray
Write-Host "  - Uses pythonw.exe (no console window)" -ForegroundColor Gray
Write-Host "  - 'Run whether user is logged on or not' enabled" -ForegroundColor Gray
Write-Host "  - MultipleInstances: IgnoreNew (prevents duplicate starts)" -ForegroundColor Gray
Write-Host ""
Write-Host "Verify: taskschd.msc -> search 'RinAISecretary'" -ForegroundColor Gray
Write-Host "Manual start: scripts\start_server.bat" -ForegroundColor Gray
Write-Host "Manual stop:  scripts\stop_server.bat" -ForegroundColor Gray
