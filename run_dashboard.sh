#!/usr/bin/env bash
# GeoSupply AI — launch the OSINT dashboard + REST API (macOS / Linux).
#
#   ./run_dashboard.sh            # port 8000
#   PORT=8090 ./run_dashboard.sh  # custom port
set -euo pipefail

cd "$(dirname "$0")"

# Use the project venv if present and not already active.
if [[ -z "${VIRTUAL_ENV:-}" && -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Run from source without requiring `pip install -e .`.
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
PORT="${PORT:-8000}"

if ! python -c "import fastapi, uvicorn, httpx" 2>/dev/null; then
  echo "Dependencies missing. Install them with:" >&2
  echo "    pip install -r requirements-osint.txt" >&2
  exit 1
fi

echo "GeoSupply OSINT dashboard  ->  http://localhost:${PORT}/"
echo "API docs                   ->  http://localhost:${PORT}/docs"
exec python -m uvicorn geosupply.api.main:app --host 0.0.0.0 --port "${PORT}" "$@"
