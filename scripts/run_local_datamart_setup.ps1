# One-shot local setup for datamart (v1.5)
# Run from repo root: .\scripts\run_local_datamart_setup.ps1

$ErrorActionPreference = "Stop"
$Backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $Backend
$env:PYTHONPATH = "."

Write-Host "=== Datamart local setup (offline eval) ===" -ForegroundColor Cyan
python tools/run_pipeline_eval.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "=== Datamart unit tests (pipeline CI) ===" -ForegroundColor Cyan
python -m pytest tests/datamart/test_question_bank_link_ci.py tests/datamart/test_s5_knowledge_and_resolve.py tests/datamart/test_s6_pipeline_meta.py tests/datamart/test_datamart_eval_ci.py -q --tb=short
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "=== Semantic catalog refresh (needs warehouse) ===" -ForegroundColor Cyan
python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --write
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: catalog refresh failed. Fix warehouse and re-run." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Tenant registry seed (optional) ===" -ForegroundColor Cyan
python tools/seed_demo_tenant_registry_warehouse.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: registry seed skipped or failed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. API: cd backend; python -m uvicorn app.main:app --reload" -ForegroundColor Green
Write-Host "UI: cd frontend; npm run dev" -ForegroundColor Green
