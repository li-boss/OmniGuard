$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root 'setup.ps1')
& (Join-Path $root 'start-dev.ps1') -Restart
$frontendUrl = if ($env:FENGONG_FRONTEND_URL) { $env:FENGONG_FRONTEND_URL } else { 'http://127.0.0.1:5173' }
Start-Process $frontendUrl
