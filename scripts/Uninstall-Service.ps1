#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Removes the jellyfin-debrid Windows service.
.DESCRIPTION
    Stops and uninstalls the jellyfin-debrid service registered with Servy.
#>

$ErrorActionPreference = 'Stop'

if (-not (Get-Command servy-cli -ErrorAction SilentlyContinue)) {
    Write-Error "servy-cli not found. Install Servy first: winget install servy"
    exit 1
}

Write-Host "Stopping jellyfin-debrid service..." -ForegroundColor Cyan
servy-cli stop --name="jellyfin-debrid" --quiet 2>$null

Write-Host "Uninstalling jellyfin-debrid service..." -ForegroundColor Cyan
servy-cli uninstall --name="jellyfin-debrid" --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "Service removed successfully." -ForegroundColor Green
} else {
    Write-Error "Service removal failed. Make sure you're running as Administrator."
}
