# Venv Bootstrap - Actual State

## Purpose
This document defines the current local environment bootstrap flow for GeoSupply on Windows.

## Script
Use `scripts/venv_bootstrap.ps1`.

What it does:
- Creates `.venv` if missing (or recreates with `-Recreate`)
- Upgrades `pip`, `setuptools`, `wheel`
- Computes a config hash over:
  - `pyproject.toml`
  - `requirements.txt`
  - `scripts/venv_bootstrap.ps1`
  - `sitecustomize.py`
- Stores sync state in `.venv/.bootstrap-state.json`
- Reinstalls only when drift is detected (or `-ForceSync` is used)
- Optionally installs dev extras with `-InstallDev`
- Verifies runtime via strict audit categories

## Commands
```powershell
powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1
powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -InstallDev
powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -Recreate -InstallDev
powershell -ExecutionPolicy Bypass -File scripts/venv_bootstrap.ps1 -ForceSync
```

## Venv Execution Standard
Preferred gate command:
```powershell
f:/GeoSupply/.venv/Scripts/python.exe -m geosupply.cli.audit --level strict
```

## Notes
- `sitecustomize.py` auto-adds `src/` to `sys.path` when Python is run from repo root.
- This removes manual `PYTHONPATH` requirements for local venv execution from workspace root.
