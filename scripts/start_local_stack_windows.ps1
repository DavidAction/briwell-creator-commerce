param(
    [int]$ApiPort = 8030,
    [int]$DashboardPort = 8070
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$BackendScript = Join-Path $RepoRoot "scripts\start_backend_windows.ps1"
$DashboardScript = Join-Path $RepoRoot "scripts\start_dashboard_windows.ps1"

if (-not (Test-Path $BackendScript)) {
    throw "Backend start script not found: $BackendScript"
}
if (-not (Test-Path $DashboardScript)) {
    throw "Dashboard start script not found: $DashboardScript"
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$BackendScript`"",
    "-Port", "$ApiPort"
) -WindowStyle Normal

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$DashboardScript`"",
    "-Port", "$DashboardPort"
) -WindowStyle Normal

Write-Host "Backend starting at http://127.0.0.1:$ApiPort"
Write-Host "Dashboard starting at http://127.0.0.1:$DashboardPort"
Write-Host "API docs: http://127.0.0.1:$ApiPort/docs"

