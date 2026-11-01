@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo Smart Image Compressor virtual environment was not found.
  echo Set up Python 3.11, then run:
  echo   py -3.11 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

".venv\Scripts\python.exe" -c "import fastapi, multipart, PIL, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Required packages are missing from .venv.
  echo Install them with:
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
