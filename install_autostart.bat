@echo off
schtasks /create /tn jellyfin_debrid /sc ONSTART /DELAY 0000:30 /RL HIGHEST /NP /tr "E:\DockerDesktopWSL\jellyfin_debrid\start_all_services.bat" /f
echo jellyfin_debrid service installed successfully!
echo The service will start automatically 30 seconds after Windows boots.
pause
