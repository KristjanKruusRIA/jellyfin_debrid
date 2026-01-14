@echo off
schtasks /delete /tn jellyfin_debrid /f
echo jellyfin_debrid service uninstalled successfully!
pause
