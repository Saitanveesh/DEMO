@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install Python and try again.
  pause
  exit /b 1
)
echo Crypto Cyber Hunt - local server
python app.py serve --host 127.0.0.1 --port 8000
pause
