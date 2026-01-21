@echo off
echo Stopping jellyfin_debrid service...
schtasks /end /tn jellyfin_debrid 2>nul
timeout /t 2 /nobreak >nul
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq jellyfin_debrid*" 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq jellyfin_debrid*" 2>nul
echo.
echo Service stopped. You may need to run this as Administrator if processes are still running.
pause
