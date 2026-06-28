# PostgreSQL backup via Docker Compose (Windows PowerShell)
param(
    [int]$RetentionDays = 14
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$backups = Join-Path $Root "backups"
New-Item -ItemType Directory -Force -Path $backups | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$out = Join-Path $backups "wallviz_$stamp.sql.gz"

Write-Host "Dumping database to $out ..."
docker compose exec -T postgres pg_dump -U wallviz -d wallviz --no-owner --no-acl |
    gzip > $out

if (Test-Path $out) {
    $size = (Get-Item $out).Length / 1MB
    Write-Host ("Done: {0:N2} MB" -f $size)
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $backups -Filter "wallviz_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Write-Host "Retention: $RetentionDays days"
