param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "work\briwell_mvp_app"
$DashboardDir = Join-Path $RepoRoot "work\briwell_dashboard_app"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return "python"
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return "py -3"
    }
    throw "Python 3 is required. Install Python 3.11+ or 3.12+ and rerun this script."
}

Write-Step "Checking repository"
if (-not (Test-Path $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}
if (-not (Test-Path $DashboardDir)) {
    throw "Dashboard directory not found: $DashboardDir"
}

Write-Step "Enabling git auto-push hook for this clone"
if (Test-Path (Join-Path $RepoRoot ".git")) {
    git -C $RepoRoot config core.hooksPath .githooks
    Write-Host "Git hooks path set to .githooks"
} else {
    Write-Host "Git repository not detected. Skipping hook setup."
}

Write-Step "Preparing backend environment"
$PythonCommand = Resolve-PythonCommand
if (-not (Test-Path $VenvPython)) {
    Push-Location $BackendDir
    try {
        Invoke-Expression "$PythonCommand -m venv .venv"
    } finally {
        Pop-Location
    }
}

if (-not $SkipInstall) {
    Push-Location $BackendDir
    try {
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r requirements.txt
    } finally {
        Pop-Location
    }
}

$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created local backend .env from .env.example"
} else {
    Write-Host "Existing backend .env kept"
}

Write-Step "Checking dashboard runtime"
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
    Write-Host "Node.js not found. Dashboard can still run with Python http.server, but JS smoke tests are skipped."
}

Write-Step "Setup complete"
Write-Host "Run backend:   powershell -ExecutionPolicy Bypass -File scripts\start_backend_windows.ps1"
Write-Host "Run dashboard: powershell -ExecutionPolicy Bypass -File scripts\start_dashboard_windows.ps1"
Write-Host "Run both:      powershell -ExecutionPolicy Bypass -File scripts\start_local_stack_windows.ps1"

