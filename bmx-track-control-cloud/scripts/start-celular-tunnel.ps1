# Acceso desde celular vía Internet (funciona aunque la WiFi de oficina bloquee dispositivos).
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\start-celular-tunnel.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    Write-Host "Instalando cloudflared..." -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    if (-not (Test-Path $cloudflared)) {
        throw "No se encontro cloudflared. Reinicia PowerShell e intenta de nuevo."
    }
}

$listening = netstat -an | Select-String "0\.0\.0\.0:8000.*LISTENING"
if (-not $listening) {
    Write-Host "Iniciando servidor en puerto 8000..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$ProjectRoot'; uvicorn app.main:app --reload --reload-dir app --reload-exclude '.venv' --reload-exclude '**/.venv/**' --host 0.0.0.0 --port 8000"
    )
    Start-Sleep -Seconds 4
}

Write-Host ""
Write-Host "=== BMX Track Control — túnel para celular ===" -ForegroundColor Cyan
Write-Host "Creando URL publica (Cloudflare). Espera unos segundos..." -ForegroundColor Yellow
Write-Host "Abre en el celular la URL que aparece abajo + /login" -ForegroundColor DarkGray
Write-Host "Ejemplo: https://xxxx.trycloudflare.com/login" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Mantén esta ventana abierta. Ctrl+C cierra el túnel." -ForegroundColor DarkGray
Write-Host ""

& $cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate
