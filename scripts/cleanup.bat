@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo The project virtual environment was not found. Run scripts\setup.bat first.
  exit /b 1
)

".venv\Scripts\python.exe" -m app.cleanup
if errorlevel 1 exit /b 1
