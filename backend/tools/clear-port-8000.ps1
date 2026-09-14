# Stop any process listening on port 8000 (fixes stale localhost API on Windows).
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "Port 8000 is free."
    exit 0
}
$pids = $conns.OwningProcess | Sort-Object -Unique
foreach ($procId in $pids) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    Write-Host "Stopping PID $procId ($($proc.ProcessName)) listening on 8000..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1
$left = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($left) {
    Write-Host "WARNING: port 8000 still in use."
    exit 1
}
Write-Host "Port 8000 is now free."
