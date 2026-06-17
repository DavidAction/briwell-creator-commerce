$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = Resolve-Path (Join-Path $ScriptRoot "..")
$DashboardRoot = Join-Path $WorkspaceRoot "work\briwell_dashboard_app"
$PythonPath = Join-Path $WorkspaceRoot "work\briwell_mvp_app\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
  $PythonPath = "python"
}

Start-Process `
  -FilePath $PythonPath `
  -ArgumentList @("-m", "http.server", "8070", "-b", "127.0.0.1", "-d", $DashboardRoot) `
  -WorkingDirectory $DashboardRoot `
  -WindowStyle Hidden

Write-Output "Briwell dashboard server started at http://127.0.0.1:8070"
