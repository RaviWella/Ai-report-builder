# Run datamart question bank: 10 sets × 6 questions (parallel by default).
# From repo root:  .\scripts\run_question_bank_sets.ps1
# One set only:    .\scripts\run_question_bank_sets.ps1 -Set 3
# Sequential:      .\scripts\run_question_bank_sets.ps1 -Sequential

param(
    [int]$Set = 0,  # 0 = run all sets
    [string]$Tenant = "demo_tenant",
    [switch]$Sequential
)

$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
if (-not (Test-Path $backend)) {
    $backend = Join-Path $PSScriptRoot "..\mint-analytics-v1.5\backend"
}
Push-Location $backend
$env:PYTHONPATH = "."

$reportsDir = Join-Path $backend "tools\question_bank_reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

function Run-Set([int]$n) {
    Write-Host "`n========== Set $n / 10 (6 questions) ==========" -ForegroundColor Cyan
    $out = Join-Path $reportsDir "set_$n.json"
    python tools/run_question_bank_eval.py --tenant $Tenant --set $n --json $out
    if ($LASTEXITCODE -ne 0) { throw "Set $n failed (exit $LASTEXITCODE)" }
}

try {
    if ($Set -ge 1 -and $Set -le 10) {
        Run-Set $Set
    }
    else {
        $parallelArgs = @("--all-sets", "--tenant", $Tenant)
        if ($Sequential) { $parallelArgs += "--sequential" }
        else { $parallelArgs += "--parallel" }
        Write-Host "Running 10 sets (6 questions each)..." -ForegroundColor Cyan
        python tools/run_question_bank_eval.py @parallelArgs
        if ($LASTEXITCODE -ne 0) { throw "Parallel eval failed (exit $LASTEXITCODE)" }
        Write-Host "`nReports: $reportsDir" -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
