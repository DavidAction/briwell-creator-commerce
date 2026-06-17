@echo off
set SCRIPT_DIR=%~dp0
set WORKSPACE_ROOT=%SCRIPT_DIR%..
set DASHBOARD_ROOT=%WORKSPACE_ROOT%\work\briwell_dashboard_app
set PYTHON_PATH=%WORKSPACE_ROOT%\work\briwell_mvp_app\.venv\Scripts\python.exe

if not exist "%PYTHON_PATH%" (
  set PYTHON_PATH=python
)

echo Briwell dashboard server: http://127.0.0.1:8070
"%PYTHON_PATH%" -m http.server 8070 -b 127.0.0.1 -d "%DASHBOARD_ROOT%"
