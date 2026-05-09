# GeoSupply AI — Production Rectification Guide

> **Date:** 2026-05-09  
> **Target:** Promote GeoSupply from prototype (5.4/10) to production-ready (9+/10)  
> **Priority order:** P0 (blocking) → P1 (high) → P2 (recommended)

---

## Gap Summary

| Layer | Status | Priority |
|---|---|---|
| API startup + routing | ✅ Works | — |
| Tier-0 NLP (sentiment, NER, claims) | ✅ Works — pure Python, no LLM | — |
| Task orchestration + budget gating | ✅ Works | — |
| Health / registry / budget / audit endpoints | ✅ Works | — |
| Tier-2/3 LLM inference (verification, briefs) | ❌ Stubs — no model loaded | **P0** |
| Database persistence | ❌ In-memory only, lost on restart | **P0** |
| Authentication / JWT | ❌ Stub agents | **P0** |
| Knowledge Graph | ❌ Stub agents | **P1** |
| External ingestion (NewsAPI, ACLED, etc.) | ❌ Fails silently without API keys | **P1** |

---

## P0 — Blocking (must fix before any real-world usage)

---

### GAP 1 — Tier-2/3 LLM Inference (❌ → ✅)

**Problem:** `VerifierWorker` (Tier-3) and `TranslationWorker` (Tier-2) return
rule-based stubs. `BriefSynthSubAgent` proposers call `NLPPipelineSubAgent`,
`RAGPipelineSubAgent`, and `GraphRAGSubAgent` which themselves rely on stubs.
Claims are "verified" by regex pattern-matching alone.

**Root cause:** No LLM backend configured. Workers need either a local Ollama
model or the Anthropic API.

#### Fix Option A — Anthropic Claude Haiku 4.5 (recommended, cloud)

Already implemented via `ClaudeWorkerMixin` (see `src/geosupply/workers/claude_mixin.py`).
`VerifierWorker` and `TranslationWorker` now use Claude with heuristic fallback.

**Steps to activate:**

```bash
# 1. Install the Anthropic SDK
pip install "anthropic>=0.40.0"

# 2. Set your API key (add to .env and load with python-dotenv)
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. Verify the mixin is active — run a quick smoke test
python - <<'EOF'
import asyncio
from geosupply.workers.verifier_worker import VerifierWorker
async def test():
    w = VerifierWorker()
    r = await w.process({"text": "India exports 10M tonnes of rice", "evidence": "confirmed by ministry", "trace_id": "t1"})
    print(r["result"]["verification_method"])  # should be "claude-semantic-verification"
asyncio.run(test())
EOF
```

**Cost estimate:**
- Haiku 4.5: $1.00/1M input + $5.00/1M output ≈ ₹0.08 per verification call
- Prompt caching (enabled by default in `ClaudeWorkerMixin`) reduces repeated system-prompt cost by ~90%

#### Fix Option B — Local Ollama (air-gapped / zero API cost)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the recommended models
ollama pull llama3.2:3b      # Tier-1 / NLP
ollama pull qwen2.5:14b      # Tier-2 / translation, propaganda
ollama pull llama3.3:70b-q4  # Tier-3 / verification, briefs

# 3. Set env vars
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_TIER2_MODEL="qwen2.5:14b"
export OLLAMA_TIER3_MODEL="llama3.3:70b-q4"
```

Then implement `OllamaWorkerMixin` mirroring `ClaudeWorkerMixin` but hitting
`POST http://localhost:11434/api/generate`.

**Recommendation:** Use **Option A** (Claude) for cloud deployments — it requires
zero GPU infrastructure and the prompt-caching brings the cost to under ₹5/day
for typical workloads. Use **Option B** for on-premises / defence-grade deployments.

---

### GAP 2 — Database Persistence (❌ → ✅)

**Problem:** `_TASK_STORE` in `api/dependencies.py` is a plain in-memory Python dict.
All tasks, logs, and state are lost on every server restart. `SwarmMaster` and
supervisors emit logs to SQLite (`SQLITE_PATH`), but the task registry itself is
ephemeral.

**Root cause:** No persistence layer wired to the REST task store.

#### Fix — PostgreSQL-backed task store via Supabase

```bash
pip install "supabase>=2.18.0"
```

**1. Create the table** (run once in Supabase SQL editor):

```sql
CREATE TABLE tasks (
    task_id     TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',
    payload     JSONB NOT NULL DEFAULT '{}',
    result      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tasks_status_idx ON tasks (status);
CREATE INDEX tasks_created_at_idx ON tasks (created_at DESC);
```

**2. Replace `_TASK_STORE` in `api/dependencies.py`:**

```python
import os
from supabase import create_client, AsyncClient

async def get_task_store() -> AsyncClient:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
```

**3. Update task CRUD in `api/routers/tasks.py`** to use `.table("tasks").insert/select/update`.

**4. Set env vars:**

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

#### Fix — SQLite (lightweight, single-node)

If Supabase is not available, persist to the existing SQLite file:

```python
# In api/dependencies.py — replace _TASK_STORE with SQLite-backed functions
import sqlite3, json
from geosupply.config import SQLITE_PATH

def upsert_task(task_id: str, data: dict) -> None:
    with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
        conn.execute("""
            INSERT INTO tasks (task_id, payload) VALUES (?,?)
            ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload
        """, (task_id, json.dumps(data)))

def get_task(task_id: str) -> dict | None:
    with sqlite3.connect(str(SQLITE_PATH), timeout=5.0) as conn:
        row = conn.execute("SELECT payload FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    return json.loads(row[0]) if row else None
```

**Migration SQL:**

```sql
CREATE TABLE IF NOT EXISTS tasks (
    task_id  TEXT PRIMARY KEY,
    payload  TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

### GAP 3 — Authentication / JWT (❌ → ✅)

**Problem:** `JWTAuthAgent` and `RBACPolicyAgent` exist as stub classes — they
generate placeholder tokens but do not verify them. Every API endpoint is
publicly accessible.

**Root cause:** JWT signing secret not configured; no middleware wired.

#### Fix — FastAPI JWT middleware

```bash
pip install "python-jose[cryptography]>=3.3.0" "passlib[bcrypt]>=1.7.4"
```

**1. Generate a signing secret:**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# → store as JWT_SECRET_KEY in .env
```

**2. Create `src/geosupply/api/auth.py`:**

```python
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

_SECRET  = os.environ.get("JWT_SECRET_KEY", "change-me")
_ALGO    = "HS256"
_EXPIRE  = 60 * 24  # minutes

bearer = HTTPBearer()

def create_token(sub: str, roles: list[str]) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE)
    return jwt.encode({"sub": sub, "roles": roles, "exp": exp}, _SECRET, algorithm=_ALGO)

def require_auth(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(cred.credentials, _SECRET, algorithms=[_ALGO])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(role: str):
    def _check(payload: dict = Depends(require_auth)) -> dict:
        if role not in payload.get("roles", []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' required")
        return payload
    return _check
```

**3. Add `Depends(require_auth)` to sensitive routers:**

```python
# api/routers/pipeline.py
from geosupply.api.auth import require_auth

@router.post("/run", dependencies=[Depends(require_auth)])
async def run_pipeline(...):
    ...
```

**4. Add a `/auth/token` endpoint** (POST with API key → JWT):

```python
@router.post("/token")
async def get_token(api_key: str = Body(...)):
    valid_keys = os.environ.get("API_KEYS", "").split(",")
    if api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"access_token": create_token(sub="api", roles=["operator"]), "token_type": "bearer"}
```

**5. Set env vars:**

```bash
JWT_SECRET_KEY=<your-32-byte-hex>
API_KEYS=key1,key2,key3
```

---

## P1 — High Priority

---

### GAP 4 — Knowledge Graph (❌ → ✅)

**Problem:** `GraphRAGSubAgent`, `KGCanaryAgent`, and the `/kg` router call stub
implementations. No real graph database is connected.

**Root cause:** Neo4j driver not configured; graph schema not created.

#### Fix — Neo4j AuraDB (cloud) or local Docker

```bash
pip install "neo4j>=5.0.0"
```

**1. Start Neo4j (local dev):**

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/changeme \
  neo4j:5
```

**2. Create `src/geosupply/db/graph.py`:**

```python
from __future__ import annotations
import os
from functools import lru_cache
from neo4j import AsyncGraphDatabase, AsyncDriver

@lru_cache(maxsize=1)
def get_driver() -> AsyncDriver:
    uri  = os.environ["NEO4J_URI"]        # e.g. bolt://localhost:7687
    auth = (os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    return AsyncGraphDatabase.driver(uri, auth=auth)
```

**3. Bootstrap schema** (run once):

```cypher
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (s:Supplier) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (ev:Event) REQUIRE ev.id IS UNIQUE;
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
```

**4. Wire `GraphRAGSubAgent`** to execute Cypher queries via the driver instead of
returning stubs.

**5. Set env vars:**

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
```

#### Lightweight alternative — NetworkX in-memory graph (no infra)

For single-node deployments, `networkx` is already in `pyproject.toml`. Persist
the graph to a pickle file on every write:

```python
import networkx as nx, pickle, os
_GRAPH_PATH = os.getenv("GRAPH_PICKLE_PATH", "/tmp/geosupply_kg.pkl")

def load_graph() -> nx.DiGraph:
    if os.path.exists(_GRAPH_PATH):
        with open(_GRAPH_PATH, "rb") as f:
            return pickle.load(f)
    return nx.DiGraph()

def save_graph(g: nx.DiGraph) -> None:
    with open(_GRAPH_PATH, "wb") as f:
        pickle.dump(g, f)
```

---

### GAP 5 — External Ingestion (❌ → ✅)

**Problem:** `NewsWorker`, `AISWorker`, `IndiaAPIWorker`, and `TelegramWorker`
fail silently when their API keys are missing — they return empty results with
no error surfaced to the caller.

**Root cause:** Missing API keys + no startup validation.

#### Fix Part A — Startup key validation

Add to `api/main.py` lifespan:

```python
# api/main.py — inside lifespan(), after wire_all_supervisors()
from geosupply.config import validate_required_env
validate_required_env()   # raises ValueError listing all missing keys
```

Create `src/geosupply/config.py` additions:

```python
import os, logging
logger = logging.getLogger(__name__)

_REQUIRED_KEYS: dict[str, str] = {
    "ANTHROPIC_API_KEY":      "Tier-2/3 LLM inference (VerifierWorker, TranslationWorker)",
    "SUPABASE_URL":           "Task persistence",
    "SUPABASE_SERVICE_ROLE_KEY": "Task persistence",
    "JWT_SECRET_KEY":         "API authentication",
}

_OPTIONAL_KEYS: dict[str, str] = {
    "NEWS_API_KEY":           "NewsWorker — live news ingestion",
    "ACLED_API_KEY":          "ACLEDWorker — conflict event data",
    "GDELT_API_KEY":          "GDELTWorker — global event data",
    "MARINE_TRAFFIC_API_KEY": "AISWorker — vessel tracking",
    "INDIA_ULIP_API_KEY":     "IndiaAPIWorker — ULIP logistics data",
    "IMD_API_KEY":            "IndiaAPIWorker — weather/monsoon data",
    "TELEGRAM_BOT_TOKEN":     "TelegramWorker — Telegram channel scraping",
    "NEO4J_URI":              "GraphRAGSubAgent — knowledge graph",
}

def validate_required_env() -> None:
    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise ValueError(
            "Missing required environment variables:\n"
            + "\n".join(f"  {k}  ({_REQUIRED_KEYS[k]})" for k in missing)
        )
    for k, desc in _OPTIONAL_KEYS.items():
        if not os.getenv(k):
            logger.warning("Optional env var %s not set — %s will be disabled", k, desc)
```

#### Fix Part B — Obtain the API keys

| Service | How to get key | Free tier |
|---|---|---|
| **Anthropic** | https://console.anthropic.com → API Keys | $5 free credit |
| **NewsAPI** | https://newsapi.org/register | 100 req/day free |
| **ACLED** | https://acleddata.com/register | Free academic access |
| **GDELT** | No key required — public BigQuery / REST | Free |
| **MarineTraffic** | https://www.marinetraffic.com/en/ais-api | Paid only |
| **India ULIP** | https://ulip.dpiit.gov.in → Developer Portal | Free (DPIIT approved) |
| **IMD / OpenWeather** | https://openweathermap.org/api | 1M calls/month free |
| **Telegram Bot** | `@BotFather` on Telegram | Free |
| **Supabase** | https://supabase.com → New Project | 500MB free tier |
| **Neo4j AuraDB** | https://neo4j.com/cloud/platform/aura-graph-database | 1 free instance |

#### Fix Part C — `.env` template

Create `.env.example` at project root:

```env
# ── LLM ──────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Auth ─────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY=<32-byte-hex from: python -c "import secrets; print(secrets.token_hex(32))">
API_KEYS=key1,key2

# ── Database ──────────────────────────────────────────────────────────────────
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SQLITE_PATH=./geosupply.db

# ── Knowledge Graph ───────────────────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

# ── Vector DB ─────────────────────────────────────────────────────────────────
CHROMA_HOST=localhost
CHROMA_PORT=8001

# ── External Ingestion ────────────────────────────────────────────────────────
NEWS_API_KEY=
ACLED_API_KEY=
MARINE_TRAFFIC_API_KEY=
INDIA_ULIP_API_KEY=
IMD_API_KEY=
TELEGRAM_BOT_TOKEN=

# ── Server ────────────────────────────────────────────────────────────────────
PORT=8000
```

Load in `main.py` (before any imports that read env):

```bash
pip install python-dotenv
```

```python
# Add to top of src/geosupply/api/main.py (or a bootstrap script)
from dotenv import load_dotenv
load_dotenv()
```

---

## Implementation Roadmap

### Sprint 1 — Core Functionality (Week 1)
Estimated effort: **2–3 days**

| Task | File(s) | Effort |
|---|---|---|
| Set `ANTHROPIC_API_KEY` + install `anthropic` | `.env`, `pyproject.toml` | 30 min |
| Activate `ClaudeWorkerMixin` in VerifierWorker + TranslationWorker | Already done ✅ | — |
| Smoke-test Tier-2/3 workers | manual curl or pytest | 1 hr |
| Replace `_TASK_STORE` dict with SQLite persistence | `api/dependencies.py`, `api/routers/tasks.py` | 4 hr |
| Create `.env` + `python-dotenv` setup | `.env.example`, `main.py` | 1 hr |

### Sprint 2 — Auth + Ingestion (Week 2)
Estimated effort: **3–4 days**

| Task | File(s) | Effort |
|---|---|---|
| Implement JWT auth middleware | `api/auth.py`, `api/routers/*.py` | 4 hr |
| Wire `/auth/token` endpoint | `api/routers/auth.py` | 2 hr |
| Register + obtain NewsAPI / ACLED keys | external | 1 hr |
| Add startup env validation | `config.py`, `main.py` | 2 hr |
| Fix NewsWorker to surface errors (not silent fail) | `workers/news_worker.py` | 2 hr |

### Sprint 3 — Knowledge Graph + Vector DB (Week 3)
Estimated effort: **4–5 days**

| Task | File(s) | Effort |
|---|---|---|
| Provision Neo4j AuraDB (or local Docker) | infra | 2 hr |
| Bootstrap graph schema (Cypher) | `db/graph.py` | 2 hr |
| Wire `GraphRAGSubAgent` to real Neo4j queries | `subagents/graph_rag_subagent.py` | 6 hr |
| Wire ChromaDB for RAG pipeline | `subagents/rag_pipeline_subagent.py` | 4 hr |
| Test full `run_supply_brief` DAG end-to-end | `tests/` | 4 hr |

### Sprint 4 — Production Hardening (Week 4)
Estimated effort: **3–4 days**

| Task | File(s) | Effort |
|---|---|---|
| Migrate `_TASK_STORE` to Supabase (if scaling beyond 1 node) | `api/dependencies.py` | 4 hr |
| Add `prometheus_client` metrics endpoint | `api/routers/metrics.py` | 3 hr |
| Structured logging with `structlog` (already in deps) | `api/main.py` | 2 hr |
| Docker + Compose file | `Dockerfile`, `docker-compose.yml` | 3 hr |
| Set up GitHub Actions CI (lint + test) | `.github/workflows/ci.yml` | 2 hr |

---

## Quick Verification Checklist

After each sprint, validate with:

```bash
# API health
curl http://localhost:8000/health/ping

# Tier-0 NLP (should work already)
curl -X POST http://localhost:8000/pipeline/nlp \
  -H "Content-Type: application/json" \
  -d '{"text":"India imposes tariffs on Chinese steel","trace_id":"chk1"}'

# Tier-3 verification (requires ANTHROPIC_API_KEY)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type":"CLAIM_VERIFY","payload":{"text":"India exports rice","evidence":"confirmed by ministry"},"trace_id":"chk2"}'

# Auth token (after Sprint 2)
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key":"key1"}'

# Full supply brief DAG
curl -X POST http://localhost:8000/pipeline/supply-brief \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"topic":"India wheat export ban 2025","trace_id":"chk3"}'
```

---

## Estimated Production Readiness After Each Sprint

| After | Score | Remaining gaps |
|---|---|---|
| Sprint 0 (current) | 5.4/10 | All 5 gaps open |
| Sprint 1 | 7.0/10 | Auth, KG, ingestion |
| Sprint 2 | 8.0/10 | KG, RAG pipeline |
| Sprint 3 | 9.0/10 | Metrics, Docker |
| Sprint 4 | 9.5/10 | Production-ready |

---

## Dependency Install Summary

```bash
# Core production dependencies to add to pyproject.toml
pip install \
  "anthropic>=0.40.0" \
  "mcp>=1.0.0" \
  "python-dotenv>=1.0.0" \
  "python-jose[cryptography]>=3.3.0" \
  "passlib[bcrypt]>=1.7.4" \
  "neo4j>=5.0.0"
```

Or add to `pyproject.toml` under `[project] dependencies`:

```toml
"anthropic>=0.40.0",
"mcp>=1.0.0",
"python-dotenv>=1.0.0",
"python-jose[cryptography]>=3.3.0",
"passlib[bcrypt]>=1.7.4",
"neo4j>=5.0.0",
```

---

*Document generated from production gap analysis of GeoSupply AI v0.1.0.*
*Update this document as gaps are closed.*
