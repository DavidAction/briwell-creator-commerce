$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pgBin = Join-Path $workspaceRoot "work\postgresql-17.10-portable\pgsql\bin"
$dataDir = Join-Path $workspaceRoot "work\postgres_data"

& (Join-Path $pgBin "pg_ctl.exe") -D $dataDir -m fast -w stop
Write-Host "PostgreSQL stopped"
