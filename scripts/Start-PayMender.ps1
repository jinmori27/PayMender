param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found. Complete the README quick start first."
}

$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"

Push-Location $projectRoot
try {
    & $python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "PayMender stopped with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
