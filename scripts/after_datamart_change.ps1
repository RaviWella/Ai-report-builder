<#
.SYNOPSIS
  Standard post-change workflow for Datamart (metadata + optional tests).

.DESCRIPTION
  Call after editing datamart agent code, semantic_catalog.yaml, warehouse schema,
  or backend/.env DATAMART_* / DATAHUB_* values.

.EXAMPLE
  .\scripts\after_datamart_change.ps1

.EXAMPLE
  .\scripts\after_datamart_change.ps1 -SkipTests

.EXAMPLE
  .\scripts\after_datamart_change.ps1 -LiveSmoke -ApiUrl http://127.0.0.1:8000
#>
param(
    [switch] $SkipTests,
    [switch] $SkipDatahub,
    [switch] $SkipCatalog,
    [switch] $LiveSmoke,
    [string] $ApiUrl = "",
    [switch] $LiveChat
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
& (Join-Path $here "refresh_datamart_metadata.ps1") -SkipDatahub:$SkipDatahub -SkipCatalog:$SkipCatalog

if (-not $SkipTests) {
    Write-Host "==> Datamart unit tests" -ForegroundColor Green
    $backend = Join-Path (Split-Path -Parent $here) "backend"
    Set-Location $backend
    $env:PYTHONPATH = "."
    python -m pytest tests/datamart -m datamart
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Some datamart tests failed — fix before shipping."
        exit $LASTEXITCODE
    }
}

if ($LiveSmoke) {
    Write-Host "==> Phase 10 live smoke (warehouse + optional API)" -ForegroundColor Green
    $smokeScript = Join-Path $here "smoke_datamart_phase10.ps1"
    $smokeArgs = @("-TenantId", "demo_tenant", "-ExpectProfile", "tenant_etl")
    if ($ApiUrl) { $smokeArgs += @("-ApiUrl", $ApiUrl) }
    if ($LiveChat) { $smokeArgs += "-Chat" }
    & $smokeScript @smokeArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Phase 10 live smoke failed — check DATAMART_DB_* / tenant_registry and API."
        exit $LASTEXITCODE
    }
}

Write-Host "Datamart change workflow complete." -ForegroundColor Cyan
