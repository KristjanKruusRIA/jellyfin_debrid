@echo off
REM Pre-launch wait script for jellyfin-debrid Servy service.
REM Waits 60 seconds for Docker containers to be ready before starting.
echo Waiting 60 seconds for Docker containers to start...
timeout /t 60 /nobreak >nul
echo Ready to start jellyfin-debrid.
