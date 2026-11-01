@echo off
setlocal
cd /d "%~dp0.."

py -3.11 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 was not found. Install Python 3.11 without removing your other Python versions,
  echo then run this script again.
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo The existing .venv does not use Python 3.11.
    echo Rename or remove that environment, then run this script again.
    exit /b 1
  )
) else (
  py -3.11 -m venv .venv
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo Setup complete. Start the app with scripts\start.bat.
