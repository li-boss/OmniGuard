param([switch]$Restart)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPython = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $backendPython)) {
    Write-Output 'Python environment is missing. Running setup first...'
    & (Join-Path $root 'setup.ps1')
}

function Test-PortListening {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Stop-PortProcess {
    param([int]$Port)
    $processIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

$backendPort = 5000
$frontendPort = 5173
$frontendOrigin = "http://127.0.0.1:$frontendPort"
$apiTarget = "http://127.0.0.1:$backendPort"
$env:FENGONG_FRONTEND_URL = $frontendOrigin
$env:FENGONG_BACKEND_URL = $apiTarget

if ($Restart) {
    Stop-PortProcess $backendPort
    Stop-PortProcess $frontendPort
    Start-Sleep -Milliseconds 800
}

if (-not (Test-PortListening $backendPort)) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        "`$env:API_PORT='$backendPort'; `$env:FRONTEND_ORIGIN='$frontendOrigin'; Set-Location '$root\backend'; & '$backendPython' run.py"
    )
}

if (-not (Test-PortListening $frontendPort)) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        "`$env:VITE_API_TARGET='$apiTarget'; Set-Location '$root\frontend'; npm run dev -- --port $frontendPort --host 127.0.0.1"
    )
}

Write-Output ''
Write-Output "Frontend:       $frontendOrigin"
Write-Output "Backend health: $apiTarget/api/system/health"
Write-Output 'Default login:  admin / admin123'
