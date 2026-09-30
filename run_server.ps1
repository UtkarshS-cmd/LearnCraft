# =============================================================================
# LearnCraft - Simple Server Runner (PowerShell, local / LAN / hotspot / online)
# =============================================================================
#   Local-only :  .\run_server.ps1            -> http://localhost:5000
#   LAN/hotspot:  .\run_server.ps1 -Lan       -> http://<this-PC-LAN-IP>:5000
#   Any phone  :  .\run_server.ps1 -Share     -> prints a PUBLIC https link +
#                 scannable QR code, reachable from any network (tunnel).
#                 Optional: -Tool cloudflared|ngrok|ssh  (default: auto-detect)
#   Custom port:  .\run_server.ps1 -Lan -Port 8080
#   Local-only custom port: .\run_server.ps1 -Port 8080
#
# The server prints the exact Local + LAN URLs on startup — copy the LAN URL
# to the phone/tablet. No hard-coded IP is needed (hotspot DHCP changes it).
# =============================================================================

param(
  [switch]$Lan,
  [switch]$Share,
  [string]$Tool = "",
  [int]$Port = 0
)

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
# Do not clobber user-provided values; default to local-only :5000.
if (-not $env:LEARNCRAFT_DB_PATH) { $env:LEARNCRAFT_DB_PATH = Join-Path $BackendDir "data\learncraft.db" }
if (-not $env:LEARNCRAFT_NETWORK_MODE) { $env:LEARNCRAFT_NETWORK_MODE = "OFFLINE" }
# -Share sets its own bind (LEARNCRAFT_SHARE_HOST, default 0.0.0.0) inside
# scripts/share_online.py; APP_HOST stays untouched here so mixing -Lan/-Share
# never surprises the operator.
if ($Lan -and -not $env:APP_HOST) { $env:APP_HOST = "0.0.0.0" }
if (-not $env:APP_HOST) { $env:APP_HOST = "127.0.0.1" }
if ($Port -gt 0) { $env:APP_PORT = "$Port" }
if (-not $env:APP_PORT) { $env:APP_PORT = "5000" }
if (-not $env:APP_ENV) { $env:APP_ENV = "development" }

$bindHost = $env:APP_HOST
if ($Share) {
    $bindHost = "0.0.0.0"
    if ($env:LEARNCRAFT_SHARE_HOST) { $bindHost = $env:LEARNCRAFT_SHARE_HOST }
}
Write-Host "  Secret Key:     Configured (saved in .secret_key)" -ForegroundColor Green
Write-Host "  Database:       $($env:LEARNCRAFT_DB_PATH)" -ForegroundColor Green
Write-Host "  Network Mode:   $($env:LEARNCRAFT_NETWORK_MODE)" -ForegroundColor Green
Write-Host "  Bind:           ${bindHost}:$($env:APP_PORT)  (0.0.0.0 = LAN + hotspot ready)" -ForegroundColor Green
Write-Host "  Local URL:      http://localhost:$($env:APP_PORT)" -ForegroundColor Green
Write-Host "  LAN URL:        printed below by the server - use that IP on other devices" -ForegroundColor Green
Write-Host "  Firewall (LAN): allow TCP $($env:APP_PORT) when Windows asks" -ForegroundColor Green
if ($Share) {
    Write-Host "  Share Mode:     ON - a PUBLIC https link + QR code is printed next" -ForegroundColor Yellow
    Write-Host "                  (tunnel tool auto-detected; -Tool cloudflared|ngrok|ssh)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "==============================================================================="
Write-Host ""

# Start the server (or the share/tunnel launcher when -Share is used)
cd $BackendDir
if ($Share) {
    $shareArgs = @("scripts/share_online.py", "--port", "$($env:APP_PORT)")
    if ($Tool) { $shareArgs += @("--tool", $Tool) }
    python @shareArgs
} else {
    python server.py
}
