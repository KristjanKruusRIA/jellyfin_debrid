@echo off
schtasks /create /tn jellyfin_debrid /sc ONSTART /DELAY 0005:00 /RL HIGHEST /NP /tr "\"E:\DockerDesktopWSL\jellyfin_debrid\scripts\start_all_services.bat\"" /f
if errorlevel 1 (
    echo.
    echo Warning: Task was created but may need administrator privileges.
    echo Make sure you ran this script as Administrator.
)
echo jellyfin_debrid service installed successfully!
echo The service will start automatically 2 minutes after Windows boots.
pause
