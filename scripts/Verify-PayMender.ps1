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
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency consistency check failed." }
    & $python -m pip_audit -r backend\requirements.lock
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency audit failed." }
    & $python scripts\check_secrets.py
    if ($LASTEXITCODE -ne 0) { throw "Tracked-secret scan failed." }

    Push-Location frontend
    try {
        & pnpm lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend type checking failed." }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
        & pnpm audit --prod
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency audit failed." }
        & pnpm test:e2e
        if ($LASTEXITCODE -ne 0) { throw "Browser reviewer-flow verification failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}
