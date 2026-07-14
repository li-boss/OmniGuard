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

function Test-ProjectPort {
    param([int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) {
        return $false
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
    return $null -ne $process -and $process.CommandLine -like "*$root*"
}

function Find-FreePort {
    param([int]$StartPort)
    $port = $StartPort
    while (Test-PortListening $port) {
        $port += 1
    }
    return $port
}

# Prefer ports separate from other local projects. Reuse them when this project
# is already running; otherwise move to the next available port.
$backendPort = if ((Test-ProjectPort 5001) -or -not (Test-PortListening 5001)) { 5001 } else { Find-FreePort 5002 }
$frontendPort = if ((Test-ProjectPort 5174) -or -not (Test-PortListening 5174)) { 5174 } else { Find-FreePort 5175 }
$frontendOrigin = "http://127.0.0.1:$frontendPort"
$apiTarget = "http://127.0.0.1:$backendPort"

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
