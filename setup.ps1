$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root '.venv'
$pythonExe = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path (Join-Path $root '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $root '.env')
}

if (-not (Test-Path $pythonExe)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv $venv
    } else {
        python -m venv $venv
    }
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $root 'backend\requirements.txt')

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is missing. Install Node.js first.'
}

Push-Location (Join-Path $root 'frontend')
npm install
Pop-Location

Write-Output 'Environment is ready. Run .\start-dev.ps1 to start services.'
