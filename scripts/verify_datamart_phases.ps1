<#
.SYNOPSIS
  End-to-end datamart phase verification: migrations, registry seed, tests, live smoke.

.EXAMPLE
  .\scripts\verify_datamart_phases.ps1

.EXAMPLE
  .\scripts\verify_datamart_phases.ps1 -ApiUrl http://127.0.0.1:8000 -SeedRegistry
#>
param(
    [string] $AppDbUrl = "",
    [string] $ApiUrl = "",
    [switch] $SkipMigrations,
    [switch] $SeedRegistry,
    [switch] $SkipTests,
    [switch] $SkipLiveSmoke
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"

if (-not $AppDbUrl) {
    $AppDbUrl = "postgresql+asyncpg://postgres:postgres@localhost:5438/hrm_platform"
}

Write-Host "==> Datamart phase verification" -ForegroundColor Cyan
Write-Host "    Application DB: $AppDbUrl"

Set-Location $backend
$env:PYTHONPATH = "."
$env:APPLICATION_DATABASE_URL = $AppDbUrl
$env:DATABASE_URL = $AppDbUrl
$env:APP_DATABASE_NAME = "hrm_platform"
# Live smoke uses developer backend/.env DATAMART_DB_* when set (remote hrm_wh_* is typical).
# Do not force localhost here — local hrm_wh_demo_tenant may not exist on :5438.

if (-not $SkipMigrations) {
    Write-Host "==> Alembic upgrade head" -ForegroundColor Green
    python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $ver = python -c "from sqlalchemy import create_engine,text; from app.core.application_db import application_sync_url; e=create_engine(application_sync_url()); c=e.connect(); v=c.execute(text('SELECT version_num FROM alembic_version')).scalar(); print(v or 'MISSING'); c.close()"
    Write-Host "    alembic_version: $ver"
    if ($ver -ne "0010_dm_msg_validation") {
        Write-Warning "Expected head 0010_dm_msg_validation; got $ver"
    }
}

if ($SeedRegistry) {
    Write-Host "==> Seed demo_tenant registry + warehouse pointer" -ForegroundColor Green
    python tools/seed_demo_tenant_registry_warehouse.py 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    (registry seed skipped - run scripts/seed_demo_tenant.py if needed)" -ForegroundColor Yellow
    }
}

if (-not $SkipTests) {
    Write-Host "==> Datamart unit tests (no live marker)" -ForegroundColor Green
    Remove-Item Env:DATAMART_LIVE_TEST -ErrorAction SilentlyContinue
    python -m pytest tests/datamart -q --tb=short -m "datamart and not live"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Offline golden eval (ReportSpec + broker, mocked in CI)" -ForegroundColor Green
    python -m pytest tests/datamart/test_datamart_eval_ci.py -q --tb=short
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $SkipLiveSmoke) {
    Write-Host "==> Phase 10 live smoke" -ForegroundColor Green
    $env:DATAMART_LIVE_TEST = "1"
    # Smoke uses developer DATAMART_DB_* from backend/.env when present
    $env:DATAMART_PREFER_TENANT_REGISTRY = "false"
    $smokeScript = Join-Path $PSScriptRoot "smoke_datamart_phase10.ps1"
    if ($ApiUrl -and $ApiUrl.Trim()) {
        & $smokeScript -TenantId "demo_tenant" -ExpectProfile "tenant_etl" -ApiUrl $ApiUrl.Trim()
    } else {
        & $smokeScript -TenantId "demo_tenant" -ExpectProfile "tenant_etl"
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Datamart phase verification complete." -ForegroundColor Cyan
