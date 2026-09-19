@echo off
REM =============================================================================
REM LearnCraft - Simple Server Runner
REM =============================================================================
REM This script automatically:
REM   1. Activates the virtual environment (if it exists)
REM   2. Sets a default secret key if not configured
REM   3. Starts the Flask server
REM
REM Usage: Double-click this file or run "run_server.bat" from command prompt
REM =============================================================================

setlocal EnableDelayedExpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"

REM Use py launcher as fallback if python is not in PATH
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 'python' not found in PATH, using 'py' launcher...
    set PY_CMD=py
) else (
    set PY_CMD=python
)

REM Check if venv exists, if not create it
if not exist "%BACKEND_DIR%\.venv" (
    echo [INFO] Creating virtual environment...
    %PY_CMD% -m venv "%BACKEND_DIR%\.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Make sure Python is installed.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call "%BACKEND_DIR%\.venv\Scripts\activate.bat"

REM Check if requirements are installed
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r "%BACKEND_DIR%\requirements.txt"
)

REM Set default secret key if not configured
set "SECRET_KEY_FILE=%BACKEND_DIR%\.secret_key"
if not exist "%SECRET_KEY_FILE%" (
    echo [INFO] Generating secret key...
    %PY_CMD% -c "import secrets; print(secrets.token_hex(32))" > "%SECRET_KEY_FILE%"
)

set /p LEARNCRAFT_SECRET_KEY=<"%SECRET_KEY_FILE%"

REM Set environment variables
set LEARNCRAFT_DB_PATH=%BACKEND_DIR%\data\learncraft.db
set LEARNCRAFT_NETWORK_MODE=OFFLINE

REM Display startup info
echo.
echo =============================================================================
echo  LearnCraft Server
echo =============================================================================
echo  Secret Key:     Configured (saved in .secret_key)
echo  Database:       %LEARNCRAFT_DB_PATH%
echo  Network Mode:   %LEARNCRAFT_NETWORK_MODE%
echo  Server URL:     http://localhost:5000
echo =============================================================================
echo.

REM Start the server
cd /d "%BACKEND_DIR%"
py server.py

endlocal
