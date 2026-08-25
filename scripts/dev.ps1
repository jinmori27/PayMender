$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create .venv and install backend/requirements.txt first."
}
Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--reload", "--port", "8000") -WorkingDirectory $workspace -WindowStyle Hidden
Push-Location (Join-Path $workspace "frontend")
try { pnpm dev } finally { Pop-Location }
