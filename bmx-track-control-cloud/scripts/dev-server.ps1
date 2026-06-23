# Servidor local con recarga automática (solo vigila app/, ignora .venv)
# Uso: powershell -ExecutionPolicy Bypass -File .\scripts\dev-server.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Uvicorn = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"
if (-not (Test-Path $Uvicorn)) {
    Write-Host "No se encontró el entorno virtual. Ejecuta primero:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "  pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

Write-Host "Iniciando servidor en http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Recarga automatica: solo carpeta app/" -ForegroundColor DarkGray
Write-Host ""

# Solo --reload-dir app: no hace falta --reload-exclude (PowerShell expande .venv y *.db a miles de argumentos).
& $Uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
