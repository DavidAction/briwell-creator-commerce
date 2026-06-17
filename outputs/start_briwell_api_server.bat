@echo off
setlocal
cd /d "%~dp0..\work\briwell_mvp_app"
echo Starting Briwell API server...
echo.
echo Swagger URL:
echo http://127.0.0.1:8030/docs
echo.
echo Keep this window open while using the API docs.
echo Press Ctrl+C in this window to stop the server.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8030
echo.
pause
