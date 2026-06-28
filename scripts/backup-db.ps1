# PostgreSQL backup via Docker Compose (Windows PowerShell)
param(
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Compress-GzipFile {
    param([string]$InputPath, [string]$OutputPath)
    $inStream = [System.IO.File]::OpenRead($InputPath)
    try {
        $outStream = [System.IO.File]::Create($OutputPath)
        try {
            $gzip = New-Object System.IO.Compression.GZipStream(
                $outStream,
                [System.IO.Compression.CompressionMode]::Compress
            )
            try {
                $inStream.CopyTo($gzip)
            } finally {
                $gzip.Dispose()
            }
        } finally {
            $outStream.Dispose()
        }
    } finally {
        $inStream.Dispose()
    }
}

$backups = Join-Path $Root "backups"
New-Item -ItemType Directory -Force -Path $backups | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sqlTmp = Join-Path $backups "wallviz_$stamp.sql"
$out = Join-Path $backups "wallviz_$stamp.sql.gz"

Write-Host "Dumping database to $out ..."
docker compose exec -T postgres pg_dump -U wallviz -d wallviz --no-owner --no-acl | Out-File -FilePath $sqlTmp -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed (exit $LASTEXITCODE)"
}

Compress-GzipFile -InputPath $sqlTmp -OutputPath $out
Remove-Item $sqlTmp -Force

if (Test-Path $out) {
    $size = (Get-Item $out).Length / 1MB
    Write-Host ("Done: {0:N2} MB" -f $size)
}

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem $backups -Filter "wallviz_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Write-Host "Retention: $RetentionDays days"
