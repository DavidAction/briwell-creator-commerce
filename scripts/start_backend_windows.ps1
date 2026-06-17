param(
    [int]$Port = 8030
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "work\briwell_mvp_app"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Backend virtual environment not found. Run scripts\setup_windows.ps1 first."
}

Push-Location $BackendDir
try {
    $env:USE_DATABASE = if ($env:USE_DATABASE) { $env:USE_DATABASE } else { "false" }
    & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
} finally {
    Pop-Location
}

