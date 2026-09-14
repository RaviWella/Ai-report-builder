# Optional dev helper — same as running uvicorn from backend/ (env fix is in app.main).
#
# Usage: .\run-dev.ps1
#        .\run-dev.ps1 -Port 8000
#        .\run-dev.ps1 -RefreshMetadata   # run scripts/refresh_datamart_metadata.ps1 first
#
# Equivalent:
#   cd backend
#   $env:PYTHONPATH = "."
#   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

param(
    [int] $Port = 8000,
    [string] $HostName = "0.0.0.0",
    [switch] $RefreshMetadata
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if ($RefreshMetadata) {
    $refresh = Join-Path $RepoRoot "scripts\refresh_datamart_metadata.ps1"
    if (-not (Test-Path $refresh)) {
        Write-Error "Missing $refresh"
    }
    Write-Host "Refreshing DataHub + semantic catalog before start..."
    & $refresh
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Set-Location $PSScriptRoot
$env:PYTHONPATH = "."

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
    Write-Warning "No .venv found at $VenvPython — using system python (LangChain version skew may break datamart)."
}

& $Python -c "from sqlalchemy.ext.asyncio import async_sessionmaker; import sqlalchemy; assert sqlalchemy.__version__.startswith('2.')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "SQLAlchemy 2.x required. Install deps:"
    Write-Host "  cd `"$PSScriptRoot`""
    Write-Host "  $Python -m pip install -r requirements.txt"
    exit 1
}

Write-Host "Starting API on http://${HostName}:${Port} ($(& $Python --version 2>&1))"
& $Python -m uvicorn app.main:app --host $HostName --port $Port --reload
