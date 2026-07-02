#!/usr/bin/env bash
# GeoSupply AI — one-command setup (macOS / Linux).
# Creates .venv, installs the lightweight dashboard deps, launches the dashboard.
#
#   ./setup.sh            # setup + launch on port 8000
#   ./setup.sh --full     # also install the heavy swarm extras (.[full])
#   PORT=8090 ./setup.sh  # custom port
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it from https://www.python.org/downloads/" >&2
  exit 1
fi
"$PY" - <<'CHECK'
import sys
assert sys.version_info >= (3, 10), f"Python 3.10+ required, found {sys.version.split()[0]}"
CHECK

if [[ ! -d .venv ]]; then
  echo "[1/3] Creating virtual environment (.venv)…"
  "$PY" -m venv .venv
else
  echo "[1/3] Reusing existing .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/3] Installing dependencies…"
python -m pip install --upgrade pip -q
python -m pip install -q -r requirements-osint.txt
if [[ "${1:-}" == "--full" ]]; then
  echo "      Installing FULL swarm extras (this is a large download)…"
  python -m pip install -q -e ".[full,dev]"
fi

echo "[3/3] Launching dashboard…"
exec ./run_dashboard.sh
