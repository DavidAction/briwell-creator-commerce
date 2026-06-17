$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $workspaceRoot "work\briwell_mvp_app"
$pgPasswordFile = Join-Path $workspaceRoot "work\postgres_pw.txt"
$pgPassword = (Get-Content -LiteralPath $pgPasswordFile -Raw).Trim()

& (Join-Path $PSScriptRoot "start_briwell_postgres_portable.ps1")

$env:DATABASE_URL = "postgresql://briwell:$pgPassword@127.0.0.1:55432/briwell"
$env:USE_DATABASE = "true"
Set-Location $appRoot
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8030
