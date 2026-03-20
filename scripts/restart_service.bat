@echo off
echo Restarting jellyfin-debrid service...
servy-cli restart --name="jellyfin-debrid"
if errorlevel 1 (
    echo.
    echo Failed to restart. Make sure the service is installed:
    echo   powershell -ExecutionPolicy Bypass -File "%~dp0Install-Service.ps1"
    pause
    exit /b 1
)
echo.
echo Service restarted!
echo Log viewer: http://localhost:7654
timeout /t 3
