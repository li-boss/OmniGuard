$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root 'setup.ps1')
& (Join-Path $root 'start-dev.ps1')
Start-Process 'http://127.0.0.1:5173'
