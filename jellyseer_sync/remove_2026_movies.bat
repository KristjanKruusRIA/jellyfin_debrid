@echo off
echo ========================================
echo Removing 2026 Movies from Blacklist
echo ========================================
echo.

python remove_blacklisted_by_year.py --jellyseerr-api-key MTc2ODM4MjQxODQ1NjE3NmM2ZTUzLTFmNzgtNDAwMS04ZDkwLWU5YzdiMTY5NWQzOQ== --year 2026

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Script failed
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
echo ========================================
echo Removal complete!
echo ========================================
pause
