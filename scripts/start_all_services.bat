@echo off
cd /d "%~dp0\.."
echo Starting jellyfin_debrid service in background...
echo Logs available at: http://localhost:7654
echo.

REM Start the main service
start /b "" venv\Scripts\pythonw.exe main.py --config-dir config -service > nul 2>&1

REM Start the log viewer with python.exe (not pythonw) so it can run Flask properly
start "Log Viewer" /min venv\Scripts\pythonw.exe log_viewer.py

echo Services started!
echo - Main service: Running in background
echo - Log viewer: http://localhost:7654 (minimized window)
echo.
echo To stop services, run: stop_service.bat
timeout /t 3
