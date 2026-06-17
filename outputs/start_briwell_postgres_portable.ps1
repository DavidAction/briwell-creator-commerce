$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pgBin = Join-Path $workspaceRoot "work\postgresql-17.10-portable\pgsql\bin"
$dataDir = Join-Path $workspaceRoot "work\postgres_data"
$logFile = Join-Path $workspaceRoot "work\postgres_server.log"

$existing = Get-NetTCPConnection -LocalPort 55432 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "PostgreSQL is already listening on 127.0.0.1:55432"
    exit 0
}

& (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -l $logFile -o "-p 55432 -h 127.0.0.1" -w start
Write-Host "PostgreSQL started on 127.0.0.1:55432"
