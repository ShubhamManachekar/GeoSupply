# GeoSupply AI — API Collection

Complete catalogue of every API the system exposes, consumes, and depends on.

---

## Table of Contents

1. [Internal REST API (what GeoSupply exposes)](#1-internal-rest-api)
2. [External Data APIs (what GeoSupply calls)](#2-external-data-apis)
3. [LLM Inference APIs](#3-llm-inference-apis)
4. [Infrastructure & Platform APIs](#4-infrastructure--platform-apis)
5. [Environment Variables Reference](#5-environment-variables-reference)
6. [Production Readiness Gap](#6-production-readiness-gap)

---

## 1. Internal REST API

Base URL: `http://localhost:8000` (or `PORT` env var)  
Docs: `http://localhost:8000/docs` (Swagger UI, auto-generated)

### 1.1 Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/health/deep` | Full system health: supervisor count, budget remaining, worker/agent counts |

**`GET /health` Response**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-05-09T10:00:00Z"
}
```
`status` values: `ok` | `degraded` | `error`

**`GET /health/deep` Response**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-05-09T10:00:00Z",
  "supervisors_registered": 14,
  "budget_remaining_inr": 500.0,
  "workers_count": 19,
  "agents_count": 57
}
```

---

### 1.2 Task Submission

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tasks` | Submit a single task to SwarmMaster |
| `GET` | `/tasks/{task_id}` | Poll task status and result |

**`POST /tasks` Request**
```json
{
  "task_type": "NLP_SENTIMENT",
  "priority": "P1",
  "budget_inr": 10.0,
  "payload": {
    "text": "India's supply chains face disruption amid monsoon delays."
  },
  "timeout_s": 60
}
```

`priority` values: `P0` | `P1` | `P2` | `P3`  
`budget_inr` range: `0.01` – `500.0`  
`timeout_s` range: `1` – `600`

**Valid `task_type` Values** (maps to supervisor routing table)

| task_type | Supervisor | Tier |
|-----------|-----------|------|
| `INGEST_NEWS` | IngestionSupervisor | 0 |
| `INGEST_INDIA_API` | IngestionSupervisor | 0 |
| `INGEST_TELEGRAM` | IngestionSupervisor | 0 |
| `INGEST_AIS` | IngestionSupervisor | 0 |
| `NLP_SENTIMENT` | NLPSupervisor | 1 |
| `NLP_NER` | NLPSupervisor | 1 |
| `NLP_CLAIM` | NLPSupervisor | 1 |
| `NLP_TRANSLATION` | NLPSupervisor | 2 |
| `NLP_PROPAGANDA` | NLPSupervisor | 2 |
| `QUALITY_NLP` | QualitySupervisor | 1 |
| `QUALITY_HALLUCINATION` | QualitySupervisor | 2 |
| `QUALITY_SOURCE_CRED` | QualitySupervisor | 1 |
| `INTEL_SUPPLIER` | IntelSupervisor | 0 |
| `INTEL_SANCTIONS` | IntelSupervisor | 0 |
| `INTEL_CYBER` | IntelSupervisor | 1 |
| `INTEL_VERIFY` | IntelSupervisor | 3 |
| `INTEL_AUTHOR` | IntelSupervisor | 3 |
| `ML_STRESS_SCORE` | MLSupervisor | 0 |
| `ML_CONFLICT_PREDICT` | MLSupervisor | 0 |
| `ML_SUPPLIER_RANK` | MLSupervisor | 0 |
| `ML_SANCTION_CLASSIFY` | MLSupervisor | 0 |
| `INDIA_PORT` | IndiaSupervisor | 0 |
| `INDIA_MONSOON` | IndiaSupervisor | 0 |
| `INDIA_ULIP` | IndiaSupervisor | 0 |
| `INDIA_POLITICAL` | IndiaSupervisor | 0 |
| `DASH_METRIC_PULL` | DashboardSupervisor | 0 |
| `DASH_ALERT_RENDER` | DashboardSupervisor | 0 |
| `DASH_KPI_UPDATE` | DashboardSupervisor | 0 |
| `DEV_SCHEMA_MIGRATE` | DevSupervisor | 0 |
| `DEV_LINT_CHECK` | DevSupervisor | 0 |
| `DEV_TEST_RUN` | DevSupervisor | 0 |
| `TEST_UNIT` | TestSupervisor | 0 |
| `TEST_INTEGRATION` | TestSupervisor | 0 |
| `TEST_COVERAGE` | TestSupervisor | 0 |
| `TECH_API_HEALTH` | TechSupervisor | 0 |
| `TECH_DB_CHECK` | TechSupervisor | 0 |
| `TECH_CACHE_FLUSH` | TechSupervisor | 0 |
| `MKT_TWEET_GEN` | MarketingSupervisor | 1 |
| `MKT_PREDICTION_POST` | MarketingSupervisor | 1 |
| `MKT_ANALYTICS` | MarketingSupervisor | 0 |
| `MKT_CONTENT_GEN` | MarketingSupervisor | 1 |
| `LOOPHOLE_HUNT` | LoopholeHunterSupervisor | 0 |
| `LOOPHOLE_PENTEST` | LoopholeHunterSupervisor | 0 |
| `LOOPHOLE_OVERRIDE_MONITOR` | LoopholeHunterSupervisor | 0 |
| `DR_BACKUP` | DisasterRecoverySupervisor | 0 |
| `DR_COST_PROJECTION` | DisasterRecoverySupervisor | 0 |
| `DR_RESTORE` | DisasterRecoverySupervisor | 0 |
| `DR_FAILOVER` | DisasterRecoverySupervisor | 0 |
| `INFRA_HEALTH_CHECK` | InfraSupervisor | 0 |
| `INFRA_LOG` | InfraSupervisor | 0 |
| `INFRA_MOE_ROUTE` | InfraSupervisor | 0 |
| `INFRA_BUDGET` | InfraSupervisor | 0 |
| `INFRA_ROUTE_MANAGE` | InfraSupervisor | 0 |
| `INFRA_SECURITY` | InfraSupervisor | 0 |
| `INFRA_SWARM_MANAGE` | InfraSupervisor | 0 |
| `INFRA_KG_UPDATE` | InfraSupervisor | 0 |
| `INFRA_FACT_CHECK` | InfraSupervisor | 0 |
| `SUPPLY_BRIEF` | SwarmMaster (DAG) | 1–3 |

**`POST /tasks` Response** (HTTP 202)
```json
{
  "task_id": "uuid-1234",
  "status": "queued",
  "supervisor": "NLPSupervisor",
  "estimated_cost_inr": 0.05,
  "queued_at": "2026-05-09T10:00:00Z",
  "reject_reason": null
}
```
`status` values: `queued` | `rejected`

**`GET /tasks/{task_id}` Response**
```json
{
  "task_id": "uuid-1234",
  "status": "completed",
  "result": {
    "polarity": -0.42,
    "subjectivity": 0.61,
    "confidence": 0.78
  },
  "cost_inr": 0.0
}
```
`status` values: `pending` | `running` | `completed` | `error` | `rejected` | `skipped`

---

### 1.3 Supply Brief (Compound DAG)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/brief` | Execute the full 10-task SUPPLY_BRIEF pipeline (120 s timeout) |

**`POST /brief` Request**
```json
{
  "payload": {
    "text": "Typhoon Maemi disrupts Taiwan semiconductor exports to India.",
    "source_credibility": 0.85,
    "trace_id": "trace-abc-123"
  },
  "plan_id": "optional-custom-id",
  "budget_inr": 50.0
}
```

**`POST /brief` Response**
```json
{
  "plan_id": "plan-uuid",
  "task_results": {
    "INGEST_NEWS":       { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "NLP_SENTIMENT":     { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "NLP_NER":           { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "NLP_CLAIM":         { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "QUALITY_SOURCE_CRED":{ "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "INTEL_SUPPLIER":    { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "INTEL_SANCTIONS":   { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "ML_STRESS_SCORE":   { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "INTEL_VERIFY":      { "status": "completed", "result": {...}, "cost_inr": 0.0 },
    "QUALITY_HALLUCINATION": { "status": "completed", "result": {...}, "cost_inr": 0.0 }
  },
  "total_cost_inr": 0.12,
  "generated_at": "2026-05-09T10:00:01Z"
}
```

---

### 1.4 Pipeline Status

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/pipeline/{task_id}` | Get status of any in-flight or completed pipeline task |

Response schema: same as `GET /tasks/{task_id}`

---

### 1.5 Registry

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workers` | List all registered worker class names |
| `GET` | `/agents` | List all registered agent class names |
| `GET` | `/supervisors` | List all registered supervisor class names |

**`GET /workers` Response**
```json
{
  "workers": ["SentimentWorker", "NERWorker", "ClaimWorker", "..."],
  "count": 19
}
```

---

### 1.6 Budget

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/budget` | Current budget status and alert level |
| `GET` | `/budget/history` | Historical spend records |

**`GET /budget` Response**
```json
{
  "cap_inr": 500.0,
  "reserved_inr": 12.40,
  "remaining_inr": 487.60,
  "alert_level": "NORMAL"
}
```
`alert_level` values: `NORMAL` | `WARN` | `ALERT` | `CRITICAL`  
Thresholds (from `config.py`): WARN ≥ ₹250/day, CRITICAL ≥ ₹270/day, monthly WARN ≥ ₹400

---

### 1.7 Knowledge Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/kg/query` | Query entity neighbourhood in the knowledge graph |
| `POST` | `/kg/update` | Add a new triple (entity → relation → entity) |

**`GET /kg/query` Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `entity` | string | required | Entity name to look up |
| `depth` | int | 1 | Hop depth (1–3) |
| `trace_id` | string | `""` | Propagated trace identifier |

**`GET /kg/query` Response**
```json
{
  "entity": "Tata Steel",
  "triples": [
    {"source": "Tata Steel", "relation": "SUPPLIER_OF", "target": "India Railways"},
    {"source": "Tata Steel", "relation": "LOCATED_IN", "target": "Jharkhand"}
  ],
  "node_count": 2,
  "trace_id": "trace-abc"
}
```

**`POST /kg/update` Request Body** (JSON)
```json
{
  "entity_source": "Tata Steel",
  "entity_target": "India Railways",
  "relation_type": "SUPPLIER_OF",
  "confidence": 0.91
}
```

---

### 1.8 Audit

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/audit` | Discovery counts for workers, agents, subagents, schemas |
| `GET` | `/audit/run` | Run an audit pass across specified categories |

**`GET /audit` Response**
```json
{
  "workers_discovered": 19,
  "agents_discovered": 57,
  "subagents_discovered": 13,
  "schema_count": 32,
  "last_run_at": null
}
```

**`GET /audit/run` Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `categories` | string | `"all"` | Comma-separated: `workers,agents,schemas` |
| `level` | string | `"basic"` | `basic` or `deep` |

**`GET /audit/run` Response**
```json
{
  "passed": 70,
  "failed": 0,
  "categories_run": ["workers", "agents", "schemas"],
  "run_at": "2026-05-09T10:00:05Z"
}
```

---

### 1.9 Common Error Envelope

All workers return `WorkerError` on failure (Schema #23):

```json
{
  "error_type": "API_FAILURE",
  "message": "NewsAPI key not configured",
  "worker_name": "NewsWorker",
  "retry_count": 0,
  "cost_inr": 0.0,
  "trace_id": "trace-abc",
  "timestamp": "2026-05-09T10:00:00Z"
}
```

`error_type` values: `TIMEOUT` | `API_FAILURE` | `SCHEMA_VIOLATION` | `INPUT_INVALID` | `BUDGET_EXCEEDED` | `INTERNAL`

---

## 2. External Data APIs

These are APIs that GeoSupply calls to ingest real-world data. All are optional — workers return `WorkerError` with `error_type: "API_FAILURE"` if keys are missing.

### 2.1 NewsAPI.org

| Field | Value |
|-------|-------|
| Purpose | News article ingestion for geopolitical events |
| Worker | `NewsWorker` |
| Base URL | `https://newsapi.org/v2/` |
| Auth | API key via `X-Api-Key` header |
| Endpoint used | `GET /everything?q=India+supply+chain&language=en&pageSize=20` |
| Rate limit | 100 req/day (free), unlimited (paid) |
| Cost | Free tier available |
| Env var needed | `GEOSUPPLY_NEWSAPI_KEY` |

**Minimum plan for production:** Developer ($449/month) for 250,000 req/month.

---

### 2.2 ACLED (Armed Conflict Location & Event Data)

| Field | Value |
|-------|-------|
| Purpose | Conflict event data — wars, protests, battles near supply routes |
| Worker | `IndiaAPIWorker` |
| Base URL | `https://api.acleddata.com/acled/read` |
| Auth | Email + API key as query params |
| Endpoint used | `GET /acled/read?key=KEY&email=EMAIL&country=India&limit=50` |
| Rate limit | 5,000 rows/day (free academic), higher tiers available |
| Cost | Free for academic/research, commercial licensing required for production |
| Env var needed | `GEOSUPPLY_ACLED_KEY`, `GEOSUPPLY_ACLED_EMAIL` |

---

### 2.3 GDELT Project

| Field | Value |
|-------|-------|
| Purpose | Global event database — free, no key required |
| Worker | `IndiaAPIWorker` |
| Base URL | `https://api.gdeltproject.org/api/v2/` |
| Auth | None (public) |
| Endpoint used | `GET /doc/doc?query=India+supply+chain&mode=artlist&maxrecords=25&format=json` |
| Rate limit | Reasonable use (no hard limit published) |
| Cost | Free |
| Env var needed | None |

---

### 2.4 MarineTraffic / AIS (Automatic Identification System)

| Field | Value |
|-------|-------|
| Purpose | Ship tracking — vessel positions at Indian ports |
| Worker | `AISWorker` |
| Base URL | `https://services.marinetraffic.com/api/` |
| Auth | API key |
| Endpoint used | `GET /exportvessel/v:8/KEY/protocol:jsono` |
| Rate limit | Per-credit model |
| Cost | ~$50–500/month depending on vessel count |
| Env var needed | `GEOSUPPLY_AIS_KEY` |

**Alternative (free, limited):** OpenSeaMap or manual AIS feed parsing.

---

### 2.5 India ULIP (Unified Logistics Interface Platform)

| Field | Value |
|-------|-------|
| Purpose | India government logistics data — port throughput, freight volumes |
| Worker | `IndiaULIPAgent` via `IndiaAPIWorker` |
| Base URL | `https://www.ulip.dpiit.gov.in/ulip/v1.0.0/` |
| Auth | Registration + API token |
| Endpoint used | `POST /search` (freight data, vehicle tracking) |
| Cost | Free (government API) |
| Env var needed | `GEOSUPPLY_ULIP_TOKEN` |

---

### 2.6 India Meteorological Department (IMD)

| Field | Value |
|-------|-------|
| Purpose | Monsoon forecasts affecting agricultural supply chains |
| Worker | `IndiaMonsoonAgent` |
| Base URL | `https://internal.imd.gov.in/` (or OpenWeather as alternative) |
| Auth | API key |
| Endpoint used | Rainfall forecast endpoints |
| Cost | Free (IMD) or $40/month (OpenWeather One Call) |
| Env var needed | `GEOSUPPLY_IMD_KEY` or `GEOSUPPLY_OPENWEATHER_KEY` |

---

### 2.7 Telegram MTProto API

| Field | Value |
|-------|-------|
| Purpose | Monitor Telegram channels for geopolitical signals |
| Worker | `TelegramWorker` |
| Base URL | `https://api.telegram.org/bot{TOKEN}/` |
| Auth | Bot token |
| Endpoint used | `GET /getUpdates`, `POST /sendMessage` |
| Rate limit | 30 messages/second per bot |
| Cost | Free |
| Env var needed | `GEOSUPPLY_TELEGRAM_BOT_TOKEN` |

**Note:** For channel monitoring, MTProto client (Telethon/Pyrogram) is needed instead of Bot API. Requires `GEOSUPPLY_TELEGRAM_API_ID` and `GEOSUPPLY_TELEGRAM_API_HASH` from my.telegram.org.

---

### 2.8 OFAC / UN Sanctions Lists

| Field | Value |
|-------|-------|
| Purpose | Sanctions screening for suppliers and entities |
| Worker | `SanctionsWorker` |
| Source | OFAC SDN list (US Treasury) — free download |
| URL | `https://www.treasury.gov/ofac/downloads/sdn.xml` |
| Auth | None (public) |
| Update frequency | Daily |
| Cost | Free |
| Env var needed | None (downloaded locally) |

**Alternative paid option:** Dow Jones Risk & Compliance, LexisNexis.

---

## 3. LLM Inference APIs

The intelligence layer of GeoSupply requires LLM inference at three tiers. **Currently these are not connected — all Tier-2/3 tasks return stubs.**

### 3.1 Tier-1 — Small (3B parameters)

Used by: `SentimentWorker`, `NERWorker`, `ClaimWorker`, `SourceCredWorker`, `CyberThreatWorker`

| Option | Model | API |
|--------|-------|-----|
| **Local (preferred)** | `llama3.2:3b` | Ollama (`http://localhost:11434/api/generate`) |
| **Cloud fallback** | `llama-3.2-3b-preview` | GROQ (`https://api.groq.com/openai/v1/chat/completions`) |

**Ollama setup:**
```bash
ollama pull llama3.2:3b
# Verify: curl http://localhost:11434/api/tags
```

**GROQ env var:** `GROQ_API_KEY`  
**GROQ rate limit:** 6,000 req/min on free tier (sufficient for Tier-1)

---

### 3.2 Tier-2 — Medium (14B parameters)

Used by: `TranslationWorker`, `PropagandaWorker`, `NetworkWorker`

| Option | Model | API |
|--------|-------|-----|
| **Local (preferred)** | `qwen2.5:14b` | Ollama (`http://localhost:11434/api/generate`) |
| **Cloud fallback** | `qwen-2.5-14b` | GROQ or Together AI |

**Hardware requirement for local:** 16 GB VRAM (RTX 3090 / A4000 or better)

**Ollama setup:**
```bash
ollama pull qwen2.5:14b
```

**Together AI env var:** `TOGETHER_API_KEY`  
Together AI URL: `https://api.together.xyz/v1/chat/completions`

---

### 3.3 Tier-3 — Large (20B+ parameters)

Used by: `VerifierWorker`, `AuthorWorker`, `BriefSynthSubAgent` (RAG)

| Option | Model | API |
|--------|-------|-----|
| **Cloud (preferred)** | `llama-3.3-70b-versatile` | GROQ |
| **Cloud alternative** | `claude-3-5-haiku-20241022` | Anthropic API |
| **Local (GPU-heavy)** | `gpt-oss:20b` | Ollama (requires 48 GB VRAM) |

**Anthropic API env var:** `ANTHROPIC_API_KEY`  
**Anthropic API URL:** `https://api.anthropic.com/v1/messages`

**Recommended Tier-3 choice for production:** Anthropic Claude Haiku 4.5 or GROQ `llama-3.3-70b-versatile` (cheapest + fastest at scale).

---

### 3.4 Embedding Model (for ChromaDB / RAG)

Used by: `RAGPipelineSubAgent`, `GraphRAGSubAgent`

| Option | Model | Deployment |
|--------|-------|------------|
| **Local** | `sentence-transformers/all-MiniLM-L6-v2` | In-process (already in requirements) |
| **Cloud** | `text-embedding-3-small` | OpenAI API |

The `sentence-transformers` package is already a dependency — no additional API key needed for the default local model.

---

## 4. Infrastructure & Platform APIs

### 4.1 Supabase (Auth + Storage)

| Field | Value |
|-------|-------|
| Purpose | User authentication (JWT), portal access control, secret key storage |
| Used by | `SecurityAgent`, portal module |
| Base URL | `https://{PROJECT_ID}.supabase.co` |
| Endpoints | `/auth/v1/token`, `/auth/v1/user`, `/rest/v1/{table}` |
| Env vars | `GEOSUPPLY_SUPABASE_URL`, `GEOSUPPLY_SUPABASE_KEY` |
| Cost | Free tier (50,000 MAU), Pro $25/month |
| Status | **Required for production auth — currently stubbed** |

---

### 4.2 ChromaDB (Vector Store)

| Field | Value |
|-------|-------|
| Purpose | Vector embeddings for RAG retrieval |
| Used by | `RAGPipelineSubAgent`, `GraphRAGSubAgent` |
| Deployment | Local persistent (`data/chromadb/`) or ChromaDB Cloud |
| Local setup | `pip install chromadb` (already in requirements) |
| Cloud URL | `https://api.trychroma.com` |
| Env var | `GEOSUPPLY_CHROMADB_DIR` (default: `data/chromadb`) |
| Cost | Free (local), $0.05/GB/month (cloud) |
| Status | **Graceful fallback to keyword retrieval if missing** |

---

### 4.3 SQLite (Local Database)

| Field | Value |
|-------|-------|
| Purpose | Task logs, cost tracking, brief proposals, dashboard metrics |
| Path | `data/geosupply.db` |
| Setup | Auto-created by first SQLite write |
| Tables needed | `swarm_logs`, `brief_proposals`, `budget_history`, `audit_events` |
| Env var | None (path set in `config.py`) |
| Status | **Path configured, tables NOT auto-created — migration needed** |

**Migration SQL (must be run before first use):**
```sql
CREATE TABLE IF NOT EXISTS swarm_logs (
    id TEXT PRIMARY KEY,
    agent_name TEXT,
    severity TEXT,
    message TEXT,
    cost_inr REAL DEFAULT 0.0,
    timestamp TEXT,
    trace_id TEXT
);

CREATE TABLE IF NOT EXISTS brief_proposals (
    id TEXT PRIMARY KEY,
    trace_id TEXT,
    proposal_text TEXT,
    confidence REAL,
    proposer_tier INTEGER,
    factcheck_score REAL,
    source_credibility_avg REAL,
    claim_evidence_ratio REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS budget_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    spent_inr REAL,
    task_count INTEGER,
    created_at TEXT
);
```

---

### 4.4 Neo4j (Knowledge Graph — Optional)

| Field | Value |
|-------|-------|
| Purpose | Persistent entity-relationship graph (suppliers, sanctions, geo entities) |
| Used by | `KnowledgeGraphAgent` |
| Bolt URL | `bolt://localhost:7687` |
| HTTP API | `http://localhost:7474` |
| Env vars | `GEOSUPPLY_NEO4J_URI`, `GEOSUPPLY_NEO4J_USER`, `GEOSUPPLY_NEO4J_PASSWORD` |
| Cost | Free (Community Edition), AuraDB $65/month (cloud) |
| Status | **Agent is a stub — not yet connected** |

---

### 4.5 Redis (Optional — Task Store Upgrade)

| Field | Value |
|-------|-------|
| Purpose | Replace in-memory `_TASK_STORE` with persistent, multi-process safe store |
| Used by | `api/dependencies.py` |
| URL | `redis://localhost:6379` |
| Env var | `GEOSUPPLY_REDIS_URL` |
| Cost | Free (local), $0/month–$200/month (Redis Cloud) |
| Status | **Not yet integrated — in-memory dict currently used** |

---

## 5. Environment Variables Reference

### 5.1 Required (Minimum to Start)

| Variable | Default | Description |
|----------|---------|-------------|
| `GEOSUPPLY_ENV` | `development` | Runtime environment: `development` \| `staging` \| `production` |
| `PORT` | `8000` | HTTP port for uvicorn |

### 5.2 Required for Production

| Variable | Example | Description |
|----------|---------|-------------|
| `GEOSUPPLY_SUPABASE_URL` | `https://xxx.supabase.co` | Supabase project URL |
| `GEOSUPPLY_SUPABASE_KEY` | `eyJhbGci...` | Supabase service role key |
| `GEOSUPPLY_JWT_SECRET` | `random-256-bit` | JWT signing secret (HS256) |

### 5.3 LLM Inference

| Variable | Example | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | `gsk_...` | GROQ API key for Tier-1/3 LLMs |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic Claude API (Tier-3 fallback) |
| `TOGETHER_API_KEY` | `...` | Together AI for Tier-2 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |

### 5.4 External Data APIs

| Variable | Example | Description |
|----------|---------|-------------|
| `GEOSUPPLY_NEWSAPI_KEY` | `abc123...` | NewsAPI.org key |
| `GEOSUPPLY_ACLED_KEY` | `xyz789...` | ACLED API key |
| `GEOSUPPLY_ACLED_EMAIL` | `you@co.com` | ACLED registered email |
| `GEOSUPPLY_AIS_KEY` | `mt_key...` | MarineTraffic API key |
| `GEOSUPPLY_ULIP_TOKEN` | `ulip_tok...` | India ULIP API token |
| `GEOSUPPLY_OPENWEATHER_KEY` | `ow_key...` | OpenWeather API key (monsoon data) |
| `GEOSUPPLY_TELEGRAM_BOT_TOKEN` | `123456:ABC...` | Telegram Bot API token |
| `GEOSUPPLY_TELEGRAM_API_ID` | `1234567` | Telegram MTProto app ID |
| `GEOSUPPLY_TELEGRAM_API_HASH` | `abc123...` | Telegram MTProto app hash |

### 5.5 Infrastructure

| Variable | Example | Description |
|----------|---------|-------------|
| `GEOSUPPLY_CHROMADB_DIR` | `./data/chromadb` | ChromaDB persistence path |
| `GEOSUPPLY_NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `GEOSUPPLY_NEO4J_USER` | `neo4j` | Neo4j username |
| `GEOSUPPLY_NEO4J_PASSWORD` | `password` | Neo4j password |
| `GEOSUPPLY_REDIS_URL` | `redis://localhost:6379` | Redis URL (task store) |
| `GEOSUPPLY_LOG_LEVEL` | `INFO` | Log level: `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

---

## 6. Production Readiness Gap

The API layer, orchestration, and Tier-0/1 workers are complete. The following gaps must be closed before going live.

### Blocking (system non-functional without these)

| # | Gap | What to do |
|---|-----|-----------|
| 1 | **No LLM backend connected** | Wire `GROQ_API_KEY` or local Ollama into Tier-1/2/3 workers; replace stub `process()` bodies |
| 2 | **No database migration** | Run the migration SQL in §4.3 before first request touches dashboard/DR agents |
| 3 | **No auth enforcement** | Implement JWT validation in FastAPI middleware using Supabase |

### Critical (system degrades without these)

| # | Gap | What to do |
|---|-----|-----------|
| 4 | **Task store is in-memory** | Wire Redis (`GEOSUPPLY_REDIS_URL`) or PostgreSQL as the backing store |
| 5 | **Budget not persisted** | Write budget deductions to `budget_history` table on each task completion |
| 6 | **Knowledge Graph is a stub** | Connect `KnowledgeGraphAgent` to Neo4j or SQLite-based graph |

### Recommended

| # | Gap | What to do |
|---|-----|-----------|
| 7 | **No rate limiting** | Add SlowAPI middleware (`pip install slowapi`) — 100 req/min per IP |
| 8 | **No request tracing** | Auto-generate `trace_id` (UUID4) in a FastAPI middleware if not provided |
| 9 | **No Prometheus metrics** | Add `prometheus-fastapi-instrumentator` for latency/error dashboards |
| 10 | **ChromaDB not seeded** | Ingest initial supply chain corpus so RAG returns meaningful results |

---

*Document generated: 2026-05-09 | GeoSupply v0.1.0 | 14 supervisors · 57 agents · 19 workers · 13 subagents*
