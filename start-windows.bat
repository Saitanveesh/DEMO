@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
 echo Python 3.10 or newer is required.
 pause
 exit /b 1
)
echo Starting Crypto Cyber Hunt on an available local port.
echo MON is not modified or stopped.
python start_hunt.py
pause
