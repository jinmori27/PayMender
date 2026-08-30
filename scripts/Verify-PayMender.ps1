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
    & $python -m pytest backend\tests -q
    if ($LASTEXITCODE -ne 0) { throw "Backend verification failed." }

    Push-Location frontend
    try {
        & pnpm lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend type checking failed." }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}
