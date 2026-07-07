# GeoSupply AI

India-centric geopolitical supply-chain intelligence platform — a live
**OSINT command dashboard** (world-monitor style) backed by a multi-agent
swarm. All costs tracked in INR. Open data sources only by default — the
dashboard runs at ₹0.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  →  http://localhost:8000/                               │
│     │         (dark map · live wire · risk · chokepoints ·        │
│     │          war zones · India ports · intel graph · ask-OKF)   │
│     ▼                                                             │
│  FastAPI  ──  /osint/* REST  +  /osint/ws live WebSocket stream   │
│     │                                                             │
│     ▼                                                             │
│  OsintAggregator (single writer, background scheduler)            │
│     ├─ free key-free sources: USGS · NASA EONET · GDELT ·         │
│     │   RSS wire (15 feeds) · markets · Open-Meteo                 │
│     └─ intelligence: knowledge graph · OKF knowledge engine ·     │
│         bias handler · self-improving risk projections            │
└─────────────────────────────────────────────────────────────────┘
```

---

## What you need

| Requirement | Notes |
|---|---|
| **Python 3.10+** | 3.11 or 3.12 recommended |
| **pip + venv** | ship with Python |
| **Internet access** | the dashboard pulls live public OSINT feeds |
| A modern browser | Chrome / Edge / Firefox / Safari |
| API keys | **none** for the OSINT dashboard. Keys are only needed for the full swarm (Groq/Claude/Supabase/etc.) — see `.env.example` |

The OSINT dashboard needs **no API keys and no database** — it reads only
free, public, key-free endpoints and serves a no-build-step frontend.

---

## Quick start — one command

### macOS / Linux

```bash
git clone https://github.com/ShubhamManachekar/GeoSupply.git
cd GeoSupply
./setup.sh          # creates .venv, installs deps, launches the dashboard
```

### Windows (PowerShell)

```powershell
git clone https://github.com/ShubhamManachekar/GeoSupply.git
cd GeoSupply
.\setup.ps1         # creates .venv, installs deps, launches the dashboard
```

Re-runs are instant (the venv is reused). Add `--full` / `-Full` to also
install the heavy swarm extras. After first setup you can just use
`./run_dashboard.sh` / `.\run_dashboard.ps1`.

### Docker (no Python needed)

```bash
docker compose up          # → http://localhost:8000/
```

The `geosupply-data` volume persists the self-learning state (knowledge
graph, source credibility, feedback weights, calibrated thresholds)
across container restarts.

Then open **http://localhost:8000/** — it redirects to the dashboard at `/app/`.
Interactive API docs are at **http://localhost:8000/docs**.

> First load shows structural data (chokepoints, war-zone baselines, ports)
> immediately, then live events/news/markets stream in within a few seconds
> as the background scheduler completes its first fetch.

---

## Install as a package (editable)

Recommended for development — gives you the `geosupply-*` console commands:

```bash
python3 -m venv .venv && source .venv/bin/activate    # (Windows: see above)

# Dashboard + API only (small, fast):
pip install -e .

# Dashboard + dev/test tools:
pip install -e ".[dev]"

# FULL swarm (adds ChromaDB, XGBoost, sentence-transformers, Neo4j,
# Supabase, Streamlit — large download, may compile):
pip install -e ".[full,dev]"
```

After `pip install -e .` you can run from anywhere in the venv:

```bash
geosupply-api          # start the REST API + dashboard (uvicorn)
geosupply              # run the architecture/connectivity audit
geosupply-mcp          # start the MCP server
geosupply-admin        # admin CLI
```

---

## Running it

| Goal | Command |
|---|---|
| Dashboard (script) | `./run_dashboard.sh` &nbsp;/&nbsp; `.\run_dashboard.ps1` |
| Dashboard (module) | `PYTHONPATH=src python -m uvicorn geosupply.api.main:app --port 8000` |
| Dashboard (installed) | `geosupply-api` |
| Auto-reload (dev) | add `--reload` to the uvicorn command |
| Run tests | `pip install -e ".[dev]"` then `pytest -q` |

### Configuration (environment variables — all optional)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | API/dashboard port (used by `geosupply-api`) |
| `OSINT_AUTOSTART` | `1` | `0` disables the background refresh scheduler |
| `OSINT_CORS_ORIGINS` | `*` | comma-separated allowed origins |
| `OSINT_STATE_PATH` | `data/osint_learning.json` | where self-learning state persists |

Copy `.env.example` → `.env` only if you intend to wire up the full swarm
(LLM keys, Supabase, India government APIs). The dashboard ignores it.

---

## Plans (freemium)

| Plan | Price | Unlocks |
|---|---|---|
| **FREE** | ₹0 | Full live dashboard: map, wire, risk index, chokepoints, war zones, India ports, markets, streams, focus mode, WebSocket |
| **PRO** | ₹499/mo | + OKF knowledge engine (`/osint/ask`, `/osint/okf` bundle), feedback learning, knowledge graph, source-trust profiles |
| **ENTERPRISE** | ₹4,999/mo | + Full swarm control plane: pipeline, briefs, KG, budget, audit, admin, playground, MCP |

**Self-hosted installs get ENTERPRISE (everything) by default** — the gates
only activate when a hosted operator sets `GEOSUPPLY_PLAN=FREE|PRO`.
Check your plan at `GET /osint/plan`; locked endpoints return HTTP 403
with an upgrade hint. All prices INR.

## Live data sources (all free, key-free)

USGS earthquakes · NASA EONET disasters · GDELT conflict hotspots + news ·
RSS wire (BBC, Al Jazeera, DW, France 24, The Diplomat, Defense News,
gCaptain, Splash247, The Hindu, TOI, NDTV, Hindustan Times, Economic Times,
Google News) · FX/crypto/commodities (er-api, CoinGecko, Stooq) ·
Open-Meteo (India port weather + monsoon) · RainViewer radar ·
curated official YouTube live news streams.

If a source is rate-limited or down, the dashboard serves the last good
data and flags it in the **System // Sources** panel — it never fabricates.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: geosupply` | Run via `run_dashboard` script, or set `PYTHONPATH=src`, or `pip install -e .` |
| Panels stay empty / `OFFLINE` chip | Check internet access; corporate proxies/VPNs may block the feeds |
| Port 8000 in use | `PORT=8090 geosupply-api` or `--port 8090` |
| Map tiles blank | Browser is blocking CARTO CDN — allow it or check the network |
| `pip install` compiling for hours | You ran `.[full]`; for the dashboard use `requirements-osint.txt` instead |

---

## Project layout

```
GeoSupply/
├── src/geosupply/
│   ├── api/            FastAPI app + routers (osint, health, tasks, …)
│   ├── osint/          OSINT layer: sources, aggregator, intel, KG, OKF, bias
│   ├── agents/ workers/ supervisors/ subagents/   the swarm
│   ├── orchestrator/   SwarmMaster (DAG routing)
│   └── cli/  mcp/  dashboard/
├── frontend/           no-build dashboard SPA (HTML/CSS/JS + MapLibre)
├── tests/              pytest suite (1200+ tests)
├── requirements-osint.txt   lightweight dashboard install
├── requirements.txt         full pinned dependency set
└── pyproject.toml           package + extras (.[full], .[dev])
```

For architecture and development history see `Documents/`.
