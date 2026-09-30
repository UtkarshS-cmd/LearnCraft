@echo off
REM =============================================================================
REM LearnCraft - Simple Server Runner (local / LAN / hotspot / online)
REM =============================================================================
REM   Local-only :  run_server.bat            -> http://localhost:5000
REM   LAN/hotspot:  run_server.bat lan        -> http://<this-PC-LAN-IP>:5000
REM                 (also: set APP_HOST=0.0.0.0 before running)
REM   Any phone  :  run_server.bat share      -> prints a PUBLIC https link +
REM                 scannable QR code; works from any network (tunnel).
REM                 Optional: set LEARNCRAFT_SHARE_TOOL=cloudflared|ngrok|ssh
REM   Custom port:  set APP_PORT=8080  (or pass as 2nd arg: run_server.bat lan 8080)
REM
REM The server prints the exact Local + LAN URLs on startup — copy the LAN URL
REM to the phone/tablet. No hard-coded IP is needed (hotspot DHCP changes it).
REM =============================================================================

setlocal EnableDelayedExpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"

REM --- Host / port --------------------------------------------------------
REM Default: local-only. "lan" arg (or APP_HOST env) enables 0.0.0.0.
set "APP_HOST=%APP_HOST%"
if "%~1"=="lan" set "APP_HOST=0.0.0.0"
if "%~1"=="LAN" set "APP_HOST=0.0.0.0"
if "%~1"=="hotspot" set "APP_HOST=0.0.0.0"
if "%~1"=="share" set "APP_HOST=0.0.0.0"
if "%~1"=="share" set "SHARE_MODE=1"
if "%~1"=="online" set "APP_HOST=0.0.0.0"
if "%~1"=="online" set "SHARE_MODE=1"
if "%APP_HOST%"=="" set "APP_HOST=127.0.0.1"
if not "%~2"=="" set "APP_PORT=%~2"
if "%APP_PORT%"=="" set "APP_PORT=5000"
set "APP_ENV=%APP_ENV%"
if "%APP_ENV%"=="" set "APP_ENV=development"

REM Share mode binds via the tunnel launcher; keep the banner truthful when the
REM operator pins a specific interface with LEARNCRAFT_SHARE_HOST.
if defined SHARE_MODE if defined LEARNCRAFT_SHARE_HOST set "APP_HOST=%LEARNCRAFT_SHARE_HOST%"

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

REM Set environment variables (only when the user has not set them already)
if "%LEARNCRAFT_DB_PATH%"=="" set "LEARNCRAFT_DB_PATH=%BACKEND_DIR%\data\learncraft.db"
if "%LEARNCRAFT_NETWORK_MODE%"=="" set LEARNCRAFT_NETWORK_MODE=OFFLINE

REM Display startup info (exact LAN URLs are printed by the server itself)
echo.
echo =============================================================================
echo  LearnCraft Server
echo =============================================================================
echo  Secret Key:     Configured (saved in .secret_key)
echo  Database:       %LEARNCRAFT_DB_PATH%
echo  Network Mode:   %LEARNCRAFT_NETWORK_MODE%
echo  Bind:           %APP_HOST%:%APP_PORT%  (0.0.0.0 = LAN + hotspot ready)
echo  Local URL:      http://localhost:%APP_PORT%
echo  LAN URL:        printed below by the server - use that IP on other devices
echo  Firewall (LAN): allow TCP %APP_PORT% when Windows asks
if defined SHARE_MODE (
echo  Share Mode:     ON - a PUBLIC https link + QR code is printed next
echo                  (tunnel tool auto-detected; LEARNCRAFT_SHARE_TOOL=ssh^|ngrok^|cloudflared)
)
echo =============================================================================
echo.

REM Start the server (the venv is activated above, so "python" is the venv
REM interpreter; only fall back to the py launcher when python is unavailable)
cd /d "%BACKEND_DIR%"
if defined SHARE_MODE (
    set "ENTRY=scripts\share_online.py --port %APP_PORT%"
) else (
    set "ENTRY=server.py"
)
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 'python' not found in PATH, using 'py' launcher...
    py %ENTRY%
) else (
    python %ENTRY%
)

endlocal
