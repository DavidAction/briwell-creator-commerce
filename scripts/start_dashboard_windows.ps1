param(
    [int]$Port = 8070
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DashboardDir = Join-Path $RepoRoot "work\briwell_dashboard_app"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Python is required to run the static dashboard server."
    }
}

Push-Location $DashboardDir
try {
    if ($python) {
        python -m http.server $Port --bind 127.0.0.1
    } else {
        py -3 -m http.server $Port --bind 127.0.0.1
    }
} finally {
    Pop-Location
}

