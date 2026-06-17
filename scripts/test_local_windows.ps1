$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "work\briwell_mvp_app"
$DashboardDir = Join-Path $RepoRoot "work\briwell_dashboard_app"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Backend virtual environment not found. Run scripts\setup_windows.ps1 first."
}

Push-Location $BackendDir
try {
    & $VenvPython -m pytest -q
} finally {
    Pop-Location
}

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Push-Location $DashboardDir
    try {
        node --check app.js
        node tests\smoke.mjs
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Node.js not found. Skipping dashboard JS smoke tests."
}

