$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspace ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Missing .venv. Install backend requirements first." }
& $python -m pytest (Join-Path $workspace "backend\tests") -q
Push-Location (Join-Path $workspace "frontend")
try {
    pnpm lint
    pnpm build
} finally { Pop-Location }
