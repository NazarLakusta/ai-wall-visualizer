# Register Windows Task Scheduler job for daily PostgreSQL backup.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "backup-db.ps1"
$taskName = "WallViz-DB-Backup"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""

$trigger = New-ScheduledTaskTrigger -Daily -At 3:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Daily PostgreSQL backup for AI Wall Visualizer (Docker)" `
    -Force | Out-Null

Write-Host "Scheduled task '$taskName' registered (daily 03:00)."
