# =============================================================================
# LearnCraft - Simple Server Runner (PowerShell)
# =============================================================================
# This script automatically:
#   1. Activates the virtual environment (if it exists)
#   2. Sets a default secret key if not configured
#   3. Starts the Flask server
#
# Usage: .\run_server.ps1 or right-click and "Run with PowerShell"
# =============================================================================

$ErrorActionPreference = "Stop"

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$SecretKeyFile = Join-Path $BackendDir ".secret_key"

Write-Host ""
Write-Host "==============================================================================="
Write-Host "  LearnCraft Server"
Write-Host "==============================================================================="
Write-Host ""

# Check if venv exists, if not create it
if (-not (Test-Path $VenvDir)) {
    Write-Host "[INFO] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $VenvDir
}

# Activate virtual environment
& "$VenvDir\Scripts\Activate.ps1"

# Check if requirements are installed
$flaskInstalled = Get-Command flask -ErrorAction SilentlyContinue
if (-not $flaskInstalled) {
    Write-Host "[INFO] Installing dependencies..." -ForegroundColor Cyan
    pip install -r (Join-Path $BackendDir "requirements.txt")
}

# Set default secret key if not configured
if (-not (Test-Path $SecretKeyFile)) {
    Write-Host "[INFO] Generating secret key..." -ForegroundColor Cyan
    $secretKey = python -c "import secrets; print(secrets.token_hex(32))"
    $secretKey | Out-File -FilePath $SecretKeyFile -Encoding utf8
}

$secretKey = Get-Content $SecretKeyFile
$env:LEARNCRAFT_SECRET_KEY = $secretKey.Trim()
$env:LEARNCRAFT_DB_PATH = Join-Path $BackendDir "data\learncraft.db"
$env:LEARNCRAFT_NETWORK_MODE = "OFFLINE"

Write-Host "  Secret Key:     Configured (saved in .secret_key)" -ForegroundColor Green
Write-Host "  Database:       $($env:LEARNCRAFT_DB_PATH)" -ForegroundColor Green
Write-Host "  Network Mode:   $($env:LEARNCRAFT_NETWORK_MODE)" -ForegroundColor Green
Write-Host "  Server URL:     http://localhost:5000" -ForegroundColor Green
Write-Host ""
Write-Host "==============================================================================="
Write-Host ""

# Start the server
cd $BackendDir
python server.py
