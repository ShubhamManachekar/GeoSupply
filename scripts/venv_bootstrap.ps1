<#
.SYNOPSIS
Bootstraps a local Python virtual environment for GeoSupply on Windows.

.DESCRIPTION
- Creates `.venv` if missing (or recreates with -Recreate)
- Upgrades `pip`, `setuptools`, `wheel`
- Auto-detects dependency/config changes and re-syncs installs only when needed
- Installs project in editable mode (`-e .`) and optional dev extras (`.[dev]`)
- Persists sync state in `.venv/.bootstrap-state.json`

.USAGE
  powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1
  powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -InstallDev
  powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -Recreate -InstallDev
    powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -ForceSync
#>

[CmdletBinding()]
param(
    [switch]$Recreate,
        [switch]$InstallDev,
        [switch]$ForceSync
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$StateFile = Join-Path $VenvDir ".bootstrap-state.json"

Write-Host "[GeoSupply] Repo root: $RepoRoot"

if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Host "[GeoSupply] Removing existing .venv ..."
    Remove-Item -Recurse -Force $VenvDir
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[GeoSupply] Creating virtual environment at $VenvDir ..."
    Push-Location $RepoRoot
    try {
        py -3 -m venv .venv
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $VenvPython)) {
    throw "[GeoSupply] Failed to create venv. Ensure Python launcher 'py' is installed and points to Python 3.10+."
}

Write-Host "[GeoSupply] Upgrading packaging tools ..."
& $VenvPython -m pip install --upgrade pip setuptools wheel

function Get-ConfigHash {
    param([string]$Root)

    $files = @(
        "pyproject.toml",
        "requirements.txt",
        "scripts\venv_bootstrap.ps1",
        "sitecustomize.py"
    )

    $parts = @()
    foreach ($rel in $files) {
        $full = Join-Path $Root $rel
        if (Test-Path $full) {
            $hash = (Get-FileHash -Algorithm SHA256 -Path $full).Hash
            $parts += "$rel=$hash"
        }
        else {
            $parts += "$rel=MISSING"
        }
    }

    $joined = ($parts -join "`n")
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($joined)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($bytes)
    }
    finally {
        $sha.Dispose()
    }
    return ([System.BitConverter]::ToString($digest) -replace "-", "").ToLowerInvariant()
}

function Read-State {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    try {
        return (Get-Content -Raw -Path $Path | ConvertFrom-Json)
    }
    catch {
        Write-Host "[GeoSupply] Warning: state file is invalid, forcing re-sync."
        return $null
    }
}

function Write-State {
    param(
        [string]$Path,
        [string]$ConfigHash,
        [bool]$DevInstalled
    )
    $state = [pscustomobject]@{
        config_hash = $ConfigHash
        dev_installed = $DevInstalled
        synced_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $json = $state | ConvertTo-Json -Depth 4
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

$currentHash = Get-ConfigHash -Root $RepoRoot
$previousState = Read-State -Path $StateFile
$previousHash = if ($null -ne $previousState) { [string]$previousState.config_hash } else { "" }
$previousDev = if ($null -ne $previousState) { [bool]$previousState.dev_installed } else { $false }

$needsSync = $ForceSync -or ($currentHash -ne $previousHash)
$needsDevSync = $InstallDev -and (-not $previousDev)

if ($needsSync -or $needsDevSync) {
    Write-Host "[GeoSupply] Dependency/config drift detected. Syncing environment ..."

    Push-Location $RepoRoot
    try {
        Write-Host "[GeoSupply] Installing project in editable mode ..."
        & $VenvPython -m pip install -e .

        if ($InstallDev) {
            Write-Host "[GeoSupply] Installing dev extras ..."
            & $VenvPython -m pip install -e ".[dev]"
        }
    }
    finally {
        Pop-Location
    }

    Write-State -Path $StateFile -ConfigHash $currentHash -DevInstalled $InstallDev
}
else {
    Write-Host "[GeoSupply] No dependency/config changes detected. Skipping reinstall."
}

Write-Host "[GeoSupply] Verifying audit command in venv ..."
& $VenvPython -m geosupply.cli.audit --categories breakage,logic,oversight,connectivity --level strict

Write-Host ""
Write-Host "[GeoSupply] Bootstrap complete."
Write-Host "Use this interpreter in VS Code: $VenvPython"
