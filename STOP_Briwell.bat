@echo off
title Briwell - Stop
cd /d "%~dp0"

echo Stopping Briwell (API + Dashboard)...
powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\stop_local_stack_windows.ps1"
echo.
echo Done. You can close any leftover server windows.
timeout /t 4 /nobreak >nul
