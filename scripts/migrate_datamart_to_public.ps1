# mint-analytics-v1.5 — run when ready (NOT executed automatically with mint-analytics).
# Applies all migrations including datamart consolidation to public schema (revision 0005).
#
# Prerequisites:
#   - Postgres running (see docker-compose.yml / backend/.env DATABASE_URL)
#   - backend/.env copied from backend/.env.example
#
# Usage:
#   .\scripts\migrate_datamart_to_public.ps1
#
# Override DB:
#   $env:DATABASE_URL = "postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5433/postgres"
Set-Location $PSScriptRoot\..\backend
$env:PYTHONPATH = "."
if (-not $env:DATABASE_URL) {
  Write-Warning "DATABASE_URL not set — using value from backend/.env via pydantic-settings."
}
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m alembic current
Write-Host "Done. Datamart tables should exist only in public schema."
