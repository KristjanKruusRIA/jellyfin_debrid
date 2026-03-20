@echo off
echo Starting jellyfin-debrid service...
servy-cli start --name="jellyfin-debrid"
if errorlevel 1 (
    echo.
    echo Failed to start. Make sure the service is installed:
    echo   powershell -ExecutionPolicy Bypass -File "%~dp0Install-Service.ps1"
    pause
    exit /b 1
)
echo.
echo Service started!
echo Log viewer: http://localhost:7654
echo.
echo To stop:    stop_service.bat
echo To restart: restart_service.bat
timeout /t 3
