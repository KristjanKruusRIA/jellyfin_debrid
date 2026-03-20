@echo off
REM Pre-launch wait script for jellyfin-debrid Servy service.
REM Waits 180 seconds for Docker containers to be ready before starting.
echo Waiting 180 seconds for Docker containers to start...
timeout /t 180 /nobreak >nul
echo Ready to start jellyfin-debrid.
