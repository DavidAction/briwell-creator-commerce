@echo off
title Briwell - Start
cd /d "%~dp0"

echo ================================================
echo   Starting Briwell (API + Dashboard)...
echo ================================================
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "scripts\start_local_stack_windows.ps1"

echo.
echo   Dashboard : http://127.0.0.1:8070
echo   API docs  : http://127.0.0.1:8030/docs
echo.
echo Opening the dashboard in your browser...
timeout /t 7 /nobreak >nul
start "" "http://127.0.0.1:8070"

echo.
echo Two server windows are now running (API and Dashboard).
echo To shut everything down, double-click STOP_Briwell.bat.
echo This launcher window can be closed.
timeout /t 5 /nobreak >nul
