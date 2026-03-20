@echo off
echo Stopping jellyfin-debrid service...
servy-cli stop --name="jellyfin-debrid"
if errorlevel 1 (
    echo.
    echo Failed to stop. The service may not be running or not installed.
)
echo.
pause
