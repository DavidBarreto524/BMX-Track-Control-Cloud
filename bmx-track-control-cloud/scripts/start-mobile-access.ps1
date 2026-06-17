# Arranca la app y abre el puerto 8000 para acceso desde celular (misma WiFi).
# Ejecutar desde la carpeta bmx-track-control-cloud:
#   powershell -ExecutionPolicy Bypass -File .\scripts\start-mobile-access.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ruleName = "BMX Track 8000"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    Write-Host "Creando regla de firewall (puede pedir permiso de administrador)..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -Wait -ArgumentList @(
        "-NoProfile",
        "-Command",
        "New-NetFirewallRule -DisplayName '$ruleName' -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow"
    )
}

$ip = (
    Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.*" -and
        $_.InterfaceAlias -notmatch "vEthernet|VirtualBox|VMware|Loopback"
    } |
    Select-Object -First 1
).IPAddress

Write-Host ""
Write-Host "=== BMX Track Control — acceso movil ===" -ForegroundColor Cyan
Write-Host "PC (local):     http://127.0.0.1:8000/login"
Write-Host "Celular (WiFi): http://${ip}:8000/login" -ForegroundColor Green
Write-Host ""
Write-Host "Requisitos: celular en la misma WiFi, datos moviles apagados." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Si el celular NO carga (WiFi de oficina), usa el tunel:" -ForegroundColor Yellow
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\start-celular-tunnel.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "Iniciando servidor..." -ForegroundColor Yellow
Write-Host ""

uvicorn app.main:app --reload --reload-dir app --reload-exclude ".venv" --reload-exclude "**/.venv/**" --host 0.0.0.0 --port 8000
