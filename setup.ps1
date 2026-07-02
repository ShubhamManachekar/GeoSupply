# GeoSupply AI - one-command setup (Windows PowerShell).
# Creates .venv, installs the lightweight dashboard deps, launches the dashboard.
#
#   .\setup.ps1           # setup + launch on port 8000
#   .\setup.ps1 -Full     # also install the heavy swarm extras (.[full])
#   $env:PORT=8090; .\setup.ps1
param([switch]$Full)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $python = "py" } else {
    $pycmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pycmd) {
        Write-Error "Python 3.10+ is required. Install from https://www.python.org/downloads/ (tick 'Add to PATH')."
        exit 1
    }
    $python = "python"
}

if (-not (Test-Path ".venv")) {
    Write-Host "[1/3] Creating virtual environment (.venv)..."
    & $python -m venv .venv
} else {
    Write-Host "[1/3] Reusing existing .venv"
}
& .\.venv\Scripts\Activate.ps1

Write-Host "[2/3] Installing dependencies..."
python -m pip install --upgrade pip -q
python -m pip install -q -r requirements-osint.txt
if ($Full) {
    Write-Host "      Installing FULL swarm extras (large download)..."
    python -m pip install -q -e ".[full,dev]"
}

Write-Host "[3/3] Launching dashboard..."
& .\run_dashboard.ps1
