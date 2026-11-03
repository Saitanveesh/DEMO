@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required. Install Python and try again.
  pause
  exit /b 1
)
echo Starting Crypto Cyber Hunt on an available local port.
echo Existing MON installations will not be modified.
python start_hunt.py
if errorlevel 1 (
  echo.
  echo Check the message above. If setup has not been completed, run:
  echo python setup_event.py
)
pause
