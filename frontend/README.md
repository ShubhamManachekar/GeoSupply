# GeoSupply AI — OSINT Command Dashboard (Frontend)

World-monitor-style live OSINT dashboard. Vanilla JS + MapLibre GL (CDN) —
no build step, served directly by the FastAPI backend.

## Run

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m uvicorn geosupply.api.main:app --port 8000
# open http://localhost:8000/  (redirects to /app/)
```

`OSINT_AUTOSTART=0` disables the background refresh scheduler (used in tests).
`OSINT_CORS_ORIGINS` (comma-separated) restricts CORS; defaults to `*`.

## Architecture

```
frontend/ (this SPA)        ── static files served at /app/
   js/app.js                ── data layer: /osint/ws WebSocket + REST fallback
   js/map.js                ── MapLibre dark map, 5 toggleable intel layers
   js/panels.js             ── panel renderers (brief, wire, risk, chokepoints,
                               markets, India ports, source health)
        │
        ▼
/osint/* REST + /osint/ws   ── geosupply/api/routers/osint.py (read-only views)
        │
        ▼
OsintAggregator             ── geosupply/osint/aggregator.py (single writer)
   ├─ sources/  TTL-cached, breaker-guarded, free & key-free:
   │    USGS quakes · NASA EONET disasters · GDELT conflict GEO ·
   │    GDELT news DOC · RSS wire (BBC/AJ/gCaptain/Hindu/TOI/DW) ·
   │    Markets (er-api FX, CoinGecko, Stooq) · Open-Meteo port weather
   ├─ intel.py  derived analytics: chokepoint stress, country risk,
   │            rule-based situation brief (no LLM on critical path)
   └─ hub.py    WebSocket fan-out to connected dashboards
```

All data sources are free — `cost_inr = 0.0` for the entire OSINT layer.
Failures degrade gracefully: last good payload is served from cache and the
failure surfaces in the SYSTEM // SOURCES panel, never as fabricated data.
