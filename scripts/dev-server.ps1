# Arranca el servidor desde la raíz del repo (delega a bmx-track-control-cloud).
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\dev-server.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppRoot = Join-Path $RepoRoot "bmx-track-control-cloud"
$InnerScript = Join-Path $AppRoot "scripts\dev-server.ps1"

if (-not (Test-Path $InnerScript)) {
    Write-Host "No se encontró: $InnerScript" -ForegroundColor Red
    exit 1
}

& $InnerScript
