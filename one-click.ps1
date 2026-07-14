[CmdletBinding()]
param(
    [switch]$Reinstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$setupScript = Join-Path $root 'setup.ps1'
$startScript = Join-Path $root 'start-dev.ps1'
$pythonExe = Join-Path $root '.venv\Scripts\python.exe'
$nodeModules = Join-Path $root 'frontend\node_modules'

try {
    Set-Location $root

    $pythonDependenciesReady = $false
    if (Test-Path $pythonExe) {
        try {
            & $pythonExe -c 'import flask_jwt_extended, waitress' 2>$null
            $pythonDependenciesReady = $LASTEXITCODE -eq 0
        } catch {
            $pythonDependenciesReady = $false
        }
    }

    # Install dependencies on the first run, after requirements change, or
    # when explicitly requested.
    if ($Reinstall -or -not $pythonDependenciesReady -or -not (Test-Path $nodeModules)) {
        Write-Host 'Preparing the development environment...' -ForegroundColor Cyan
        & $setupScript
    }

    Write-Host 'Starting OmniGuard...' -ForegroundColor Cyan
    $startupOutput = @(& $startScript 2>&1)
    $startupOutput | ForEach-Object { Write-Host $_ }

    $frontendUrl = $startupOutput |
        ForEach-Object { [string]$_ } |
        Where-Object { $_ -match '^Frontend:\s+(https?://\S+)' } |
        ForEach-Object { $Matches[1] } |
        Select-Object -First 1

    if (-not $frontendUrl) {
        throw 'Could not determine the frontend address from start-dev.ps1.'
    }

    $backendUrl = $startupOutput |
        ForEach-Object { [string]$_ } |
        Where-Object { $_ -match '^Backend health:\s+(https?://\S+)' } |
        ForEach-Object { $Matches[1] } |
        Select-Object -First 1

    # Give Vite a moment to begin listening before opening the page.
    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    $backendReady = $false
    if ($backendUrl) {
        for ($attempt = 1; $attempt -le 30; $attempt++) {
            try {
                $response = Invoke-WebRequest -Uri $backendUrl -UseBasicParsing -TimeoutSec 2
                if ($response.StatusCode -eq 200) {
                    $backendReady = $true
                    break
                }
            } catch {
                Start-Sleep -Seconds 1
            }
        }
    }

    if (-not $ready) {
        Write-Warning "The service is still starting. Open it later: $frontendUrl"
    } elseif (-not $backendReady) {
        throw "The backend did not become ready: $backendUrl"
    } elseif (-not $NoBrowser) {
        Start-Process $frontendUrl
    }

    Write-Host ''
    Write-Host "OmniGuard is running: $frontendUrl" -ForegroundColor Green
    Write-Host 'Default login: admin / admin123'
} catch {
    Write-Host ''
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Check that Python 3 and Node.js (npm) are installed.' -ForegroundColor Yellow
    exit 1
} finally {
    Set-Location $root
}
