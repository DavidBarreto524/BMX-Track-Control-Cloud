# Servidor local con recarga automática (solo vigila app/, ignora .venv)
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\dev-server.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "Iniciando servidor en http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Recarga automatica: solo carpeta app/ (sin .venv)" -ForegroundColor DarkGray
Write-Host ""

uvicorn app.main:app `
  --reload `
  --reload-dir app `
  --reload-exclude ".venv" `
  --reload-exclude "**/.venv/**" `
  --reload-exclude "*.db" `
  --reload-exclude "**/__pycache__/**" `
  --host 127.0.0.1 `
  --port 8000
