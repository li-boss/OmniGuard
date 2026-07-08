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

function Find-FreePort {
    param([int]$StartPort)
    $port = $StartPort
    while (Test-PortListening $port) {
        $port += 1
    }
    return $port
}

$backendPort = Find-FreePort 5000
$frontendPort = Find-FreePort 5173
$frontendOrigin = "http://127.0.0.1:$frontendPort"
$apiTarget = "http://127.0.0.1:$backendPort"

if ($backendPort -ne 5000) {
    Write-Output "Port 5000 is busy. Using backend port $backendPort."
}

if ($frontendPort -ne 5173) {
    Write-Output "Port 5173 is busy. Using frontend port $frontendPort."
}

if (-not (Test-PortListening $backendPort)) {
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        "`$env:API_PORT='$backendPort'; `$env:FRONTEND_ORIGIN='$frontendOrigin'; `$env:VIDEO_FEED_URL='/api/streams/demo.mjpg'; Set-Location '$root\backend'; & '$backendPython' run.py"
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
