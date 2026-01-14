@echo off
cd /d "%~dp0"
start /b "" venv\Scripts\pythonw.exe main.py --config-dir config -service > nul 2>&1
exit
