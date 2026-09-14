<#
.SYNOPSIS
  Phase 10 live datamart smoke (bootstrap + optional HTTP / chat).

.DESCRIPTION
  Runs in-process warehouse checks, then optional HTTP bootstrap against a running API.

.EXAMPLE
  .\scripts\smoke_datamart_phase10.ps1

.EXAMPLE
  .\scripts\smoke_datamart_phase10.ps1 -ApiUrl http://127.0.0.1:8000 -Chat
#>
param(
    [string] $TenantId = "demo_tenant",
    [string] $ExpectProfile = "tenant_etl",
    [string] $ApiUrl = "",
    [switch] $Chat,
    [switch] $SkipInProcess
)

$ErrorActionPreference = "Stop"
$backend = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
Set-Location $backend
$env:PYTHONPATH = "."
$env:DATAMART_LIVE_TENANT_ID = $TenantId
$env:DATAMART_LIVE_EXPECT_PROFILE = $ExpectProfile

$pyArgs = @("--tenant", $TenantId, "--expect-profile", $ExpectProfile)
if ($ApiUrl -and $ApiUrl.Trim()) {
    $env:DATAMART_SMOKE_URL = $ApiUrl.Trim()
    $pyArgs += @("--url", $ApiUrl.Trim())
}
if ($Chat) { $pyArgs += "--chat" }
if ($SkipInProcess) { $pyArgs += "--skip-inprocess" }

python tools/smoke_datamart_phase10.py @pyArgs
exit $LASTEXITCODE
