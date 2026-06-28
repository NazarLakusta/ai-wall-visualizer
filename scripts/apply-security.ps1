# One-time security hardening: secrets, admin passwords, DB sync, backup schedule.
param(
    [switch]$SkipSchedule,
    [switch]$SkipBackup
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function New-RandomBase64([int]$Bytes = 48) {
    $buf = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
    return [Convert]::ToBase64String($buf)
}

function New-RandomPassword([int]$Length = 20) {
    $chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%"
    -join (1..$Length | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

function Set-EnvValue {
    param([string]$Name, [string]$Value)
    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path $envPath)) {
        Copy-Item (Join-Path $Root ".env.example") $envPath
    }
    $lines = Get-Content $envPath -Encoding UTF8
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^$([regex]::Escape($Name))=") {
            $found = $true
            "$Name=$Value"
        } else {
            $line
        }
    }
    if (-not $found) { $out += "$Name=$Value" }
    Set-Content -Path $envPath -Value $out -Encoding UTF8
}

Write-Host "=== Security hardening ===" -ForegroundColor Cyan

$secretKey = New-RandomBase64
$jwtSecret = New-RandomBase64
$adminPassword = New-RandomPassword
$platformPassword = New-RandomPassword

Set-EnvValue "SECRET_KEY" $secretKey
Set-EnvValue "JWT_SECRET" $jwtSecret
Set-EnvValue "ADMIN_PASSWORD" $adminPassword
Set-EnvValue "PLATFORM_ADMIN_PASSWORD" $platformPassword

$envPath = Join-Path $Root ".env"
$adminEmail = ((Get-Content $envPath | Where-Object { $_ -match '^ADMIN_EMAIL=' }) -replace '^ADMIN_EMAIL=','').Trim()
$platformEmail = ((Get-Content $envPath | Where-Object { $_ -match '^PLATFORM_ADMIN_EMAIL=' }) -replace '^PLATFORM_ADMIN_EMAIL=','').Trim()

$credPath = Join-Path $Root "credentials.local.txt"
@"
AI Wall Visualizer — локальні облікові дані (НЕ комітити в git)
Згенеровано: $(Get-Date -Format "yyyy-MM-dd HH:mm")

Store admin:
  Email:    $adminEmail
  Password: $adminPassword

Platform admin:
  Email:    $platformEmail
  Password: $platformPassword

SECRET_KEY і JWT_SECRET оновлено в .env

ВАЖЛИВО: якщо TELEGRAM_BOT_TOKEN колись потрапляв у git — перевипустіть у @BotFather.
"@ | Set-Content $credPath -Encoding UTF8

Write-Host "Updated .env secrets and passwords." -ForegroundColor Green
Write-Host "Credentials saved to: credentials.local.txt" -ForegroundColor Yellow

Write-Host "Recreating api container to load new env..."
docker compose up -d --force-recreate api | Out-Null

Write-Host "Syncing admin password hashes in PostgreSQL..."
docker compose exec -T api python /scripts/rotate-admin-passwords.py

if (-not $SkipBackup) {
    Write-Host "Running test backup..."
    & (Join-Path $PSScriptRoot "backup-db.ps1")
}

if (-not $SkipSchedule) {
    Write-Host "Installing daily backup schedule (03:00)..."
    & (Join-Path $PSScriptRoot "install-backup-schedule.ps1")
}

Write-Host ""
Write-Host "Done. Open credentials.local.txt for new admin passwords." -ForegroundColor Green
