# GeoSupply AI - launch the OSINT dashboard + REST API (Windows PowerShell).
#
#   .\run_dashboard.ps1                 # port 8000
#   $env:PORT=8090; .\run_dashboard.ps1 # custom port
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Activate the project venv if present and not already active.
if (-not $env:VIRTUAL_ENV -and (Test-Path ".venv\Scripts\Activate.ps1")) {
    & .\.venv\Scripts\Activate.ps1
}

# Run from source without requiring `pip install -e .`.
$env:PYTHONPATH = "src"
if (-not $env:PORT) { $env:PORT = "8000" }

try {
    python -c "import fastapi, uvicorn, httpx" 2>$null
} catch {
    Write-Error "Dependencies missing. Install them with: pip install -r requirements-osint.txt"
    exit 1
}

Write-Host "GeoSupply OSINT dashboard  ->  http://localhost:$($env:PORT)/"
Write-Host "API docs                   ->  http://localhost:$($env:PORT)/docs"
python -m uvicorn geosupply.api.main:app --host 0.0.0.0 --port $env:PORT @args
