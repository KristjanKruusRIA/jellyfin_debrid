#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Registers jellyfin-debrid as a Windows service using Servy.
.DESCRIPTION
    Installs the jellyfin-debrid application as a native Windows service via
    servy-cli. The service uses AutomaticDelayedStart with a 60-second
    pre-launch wait to allow Docker containers to start first (~3 min total).
.NOTES
    Prerequisites: Install Servy via 'winget install servy'
#>

$ErrorActionPreference = 'Stop'

# Auto-detect paths relative to this script
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe   = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$WaitScript  = Join-Path $ProjectRoot 'scripts\wait-before-start.bat'
$StdoutLog   = Join-Path $ProjectRoot 'config\service-stdout.log'
$StderrLog   = Join-Path $ProjectRoot 'config\service-stderr.log'

# Verify prerequisites
if (-not (Get-Command servy-cli -ErrorAction SilentlyContinue)) {
    Write-Error "servy-cli not found. Install Servy first: winget install servy"
    exit 1
}
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe. Run setup_venv.ps1 first."
    exit 1
}

Write-Host "Installing jellyfin-debrid service..." -ForegroundColor Cyan
Write-Host "  Project root : $ProjectRoot"
Write-Host "  Python       : $PythonExe"
Write-Host ""

servy-cli install `
    --name="jellyfin-debrid" `
    --displayName="Jellyfin Debrid" `
    --description="Monitors Seerr requests, scrapes torrent sources, checks debrid caching, and downloads content." `
    --path="$PythonExe" `
    --params="main.py --config-dir config -service" `
    --startupDir="$ProjectRoot" `
    --startupType="AutomaticDelayedStart" `
    --priority="Normal" `
    --stdout="$StdoutLog" `
    --stderr="$StderrLog" `
    --enableSizeRotation `
    --rotationSize=10 `
    --enableDateRotation `
    --dateRotationType="Daily" `
    --maxRotations=3 `
    --enableHealth `
    --heartbeatInterval=30 `
    --maxFailedChecks=3 `
    --recoveryAction="RestartProcess" `
    --maxRestartAttempts=5 `
    --preLaunchPath="$WaitScript" `
    --preLaunchStartupDir="$ProjectRoot" `
    --preLaunchTimeout=90 `
    --stopTimeout=10

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Service installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  Start   : servy-cli start --name=jellyfin-debrid"
    Write-Host "  Stop    : servy-cli stop --name=jellyfin-debrid"
    Write-Host "  Restart : servy-cli restart --name=jellyfin-debrid"
    Write-Host "  Status  : servy-cli status --name=jellyfin-debrid"
    Write-Host "  Remove  : .\scripts\Uninstall-Service.ps1"
    Write-Host ""
    Write-Host "The service will auto-start ~3 minutes after boot (delayed start + 60s wait)."
    Write-Host "Log viewer available at: http://localhost:7654"
} else {
    Write-Error "Service installation failed. Make sure you're running as Administrator."
}
