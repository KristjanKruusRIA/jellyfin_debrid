# Create and configure Python virtual environment for jellyfin_debrid

$VENV_DIR = "venv"
$APP_DIR = "E:\DockerDesktopWSL\jellyfin_debrid"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "jellyfin_debrid venv Setup" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Change to application directory
Set-Location $APP_DIR

# Check Python installation
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ $pythonVersion found" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Install from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VENV_DIR) {
    Write-Host "  ⚠ Virtual environment already exists at '$VENV_DIR'" -ForegroundColor Yellow
    $response = Read-Host "  Do you want to recreate it? (y/N)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Host "  Removing existing venv..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VENV_DIR
    } else {
        Write-Host "  Using existing virtual environment" -ForegroundColor Green
        $VENV_EXISTS = $true
    }
}

if (-not $VENV_EXISTS) {
    python -m venv $VENV_DIR
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Virtual environment created successfully" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Activate virtual environment
Write-Host "[3/4] Activating virtual environment..." -ForegroundColor Yellow
$ACTIVATE_SCRIPT = Join-Path $VENV_DIR "Scripts\Activate.ps1"
if (Test-Path $ACTIVATE_SCRIPT) {
    & $ACTIVATE_SCRIPT
    Write-Host "  ✓ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  ✗ Activation script not found" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "[4/4] Installing dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Virtual environment is ready at: $VENV_DIR" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test run: .\run_service.ps1" -ForegroundColor Cyan
Write-Host "  2. Verify setup: .\verify_setup.ps1" -ForegroundColor Cyan
Write-Host "  3. Install service: .\install_service.ps1 -Install -NssmPath '<path to nssm.exe>'" -ForegroundColor Cyan
Write-Host ""
Write-Host "To manually activate the venv:" -ForegroundColor Yellow
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
