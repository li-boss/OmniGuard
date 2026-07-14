[CmdletBinding()]
param(
    [switch]$SkipSemanticAudio
)

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
if ($SkipSemanticAudio) {
    & $pythonExe -m pip install -r (Join-Path $root 'backend\requirements.txt')
} else {
    Write-Output 'Installing semantic audio detection dependencies...'
    & $pythonExe -m pip install -r (Join-Path $root 'backend\requirements-audio.txt')

    Write-Output 'Downloading and caching the YAMNet audio model...'
    $env:TF_CPP_MIN_LOG_LEVEL = '2'
    & $pythonExe -c "import tensorflow_hub as hub; hub.load('https://tfhub.dev/google/yamnet/1'); print('YAMNet is ready.')"
}

Write-Output 'Downloading face recognition and anti-spoofing models...'
& $pythonExe (Join-Path $root 'backend\core_cv\scripts\download_models.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to download the face recognition or MiniFASNet anti-spoofing model.'
}

Push-Location (Join-Path $root 'backend')
try {
    & $pythonExe -c "from core_cv.model_loader import ModelLoader; session = ModelLoader.get_liveness_net(); print('MiniFASNetV2 anti-spoofing is ready:', session.session.get_inputs()[0].shape)"
    if ($LASTEXITCODE -ne 0) {
        throw 'MiniFASNetV2 could not be loaded by ONNX Runtime.'
    }
} finally {
    Pop-Location
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is missing. Install Node.js first.'
}

Push-Location (Join-Path $root 'frontend')
npm install
Pop-Location

if ($SkipSemanticAudio) {
    Write-Output 'Environment is ready with lightweight audio detection. Run .\start-dev.ps1 to start services.'
} else {
    Write-Output 'Environment is ready, including YAMNet audio detection. Run .\start-dev.ps1 to start services.'
}
