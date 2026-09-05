@echo off
setlocal EnableExtensions

REM Backend startup script (FastAPI/Uvicorn)
REM Assumes current working directory is repo root (e:/CDNNLT/CuoiKy/NongNghiepAI)

REM Use utf-8 to avoid Vietnamese encoding issues in console
chcp 65001 >nul

REM Resolve key paths once to avoid fragile nested batch syntax
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "ACTIVATE_BAT=%VENV_DIR%\Scripts\activate.bat"
set "REQ_FILE=%SCRIPT_DIR%requirements.txt"

REM Ensure we can import "app" package from backend/app
set "PYTHONPATH=%SCRIPT_DIR%"

REM Check and create virtual environment if it does not exist
if not exist "%ACTIVATE_BAT%" goto :create_venv

call "%ACTIVATE_BAT%"
goto :start_server

:create_venv
echo [INFO] Virtual environment (venv) not found. Creating one...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment. Please install Python 3.11 or 3.12 and try again.
    pause
    exit /b 1
)

call "%ACTIVATE_BAT%"
echo [INFO] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r "%REQ_FILE%"

:start_server
REM Start server
echo [INFO] Starting backend server using virtual environment...
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

endlocal
