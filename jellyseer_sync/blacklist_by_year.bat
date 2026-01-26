@echo off
setlocal enabledelayedexpansion

echo Starting year-by-year blacklist processing...
echo.

for /L %%Y in (2015,1,2025) do (
    set /A NEXT_YEAR=%%Y+1
    echo.
    echo ========================================
    echo Processing years %%Y to !NEXT_YEAR!
    echo ========================================
    python blacklist_low_rated.py --jellyseerr-api-key MTc2ODM4MjQxODQ1NjE3NmM2ZTUzLTFmNzgtNDAwMS04ZDkwLWU5YzdiMTY5NWQzOQ== --user-id 1 --genre 27 --year-gte %%Y --year-lte !NEXT_YEAR! --max-pages 500 --blacklist-countries IN --skip-blacklist-check
    
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo ERROR: Script failed for years %%Y-!NEXT_YEAR!
        echo Press any key to exit...
        pause >nul
        exit /b 1
    )
)

echo.
echo ========================================
echo All years processed successfully!
echo ========================================
pause
