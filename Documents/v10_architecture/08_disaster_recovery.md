# Chapter 8: Disaster Recovery, Backup Strategy, Cost Projection & Watchdogs

## Disaster Recovery Plan (v10)

### Recovery Objectives

```
RTO (Recovery Time Objective): 4 hours
    From total system failure to operational pipeline.

RPO (Recovery Point Objective):
    Knowledge Graph:  6 hours (backed up every pipeline run)
    ChromaDB:         24 hours (daily backup)
    SQLite:           24 hours (daily backup)
    Config:           7 days (weekly backup)
    Code:             0 hours (GitHub — always current)
    Logs:             0 hours (Supabase — cloud, always current)
```

### Backup Architecture

```
LOCAL SYSTEM                           CLOUD BACKUP
┌──────────────┐    BackupWorker    ┌──────────────────┐
│ ChromaDB     │ ──── daily ──────► │ Google Drive      │
│ (vectors)    │                    │ /geosupply/       │
├──────────────┤    BackupWorker    │   chromadb/       │
│ SQLite       │ ──── daily ──────► │   sqlite/         │
│ (structured) │                    │   kg/             │
├──────────────┤    BackupWorker    │   config/         │
│ Knowledge    │ ── every 6hr ────► │                   │
│ Graph (NX)   │                    │ AES-256 encrypted │
├──────────────┤    BackupWorker    │ 30-day retention  │
│ Config       │ ── weekly ───────► │ 12-month weekly   │
└──────────────┘                    └──────────────────┘

ALWAYS LIVE (no backup needed):
    GitHub     → all code, configs, docs
    Supabase   → all logs, audit trails
    Groq       → stateless API (no data)
```

### Recovery Procedures

```
SCENARIO 1: PC Hardware Failure
    1. Acquire replacement PC (RTX 5060 or equivalent)
    2. Clone GitHub repo (10 min)
    3. Install dependencies: pip install -r requirements.txt (5 min)
    4. Download Ollama models (30 min)
    5. Restore ChromaDB from Google Drive (decrypt + import, 30 min)
    6. Restore SQLite from Google Drive (decrypt + import, 10 min)
    7. Restore KnowledgeGraph from Google Drive (decrypt + load, 10 min)
    8. Restore config from Google Drive (5 min)
    9. Run smoke test: geosupply status (2 min)
    10. Run first pipeline: geosupply pipeline run (12 min)
    TOTAL: ~2 hours

SCENARIO 2: Data Corruption (ChromaDB/SQLite)
    1. Stop pipeline: geosupply pipeline pause
    2. Identify corruption scope
    3. Restore from last good backup (BackupWorker)
    4. Re-run affected pipeline stages
    5. Verify with LoopholeHunter: geosupply loophole run
    TOTAL: ~1 hour

SCENARIO 3: Security Breach (API Key Leaked)
    1. EMERGENCY HALT: geosupply override halt
    2. Rotate ALL keys: geosupply security rotate all
    3. Audit logs for unauthorized access
    4. Run PenTestAgent: verify no remaining access
    5. Release: geosupply override release
    TOTAL: ~30 minutes
```

---

## Cost Projection System

```python
class CostProjectionAgent(BaseAgent):
    """
    Forward-looking INR cost estimation.

    DATA SOURCES:
        - Last 7 days cost history from Supabase swarm_logs
        - Current pipeline schedule (interval hours)
        - Model usage distribution (Tier 1/2/3 ratio)

    PROJECTIONS:
        Daily projection:   (last 7-day avg cost/day) × 1.0
        Weekly projection:  daily × 7 × 1.05 (5% buffer)
        Monthly projection: daily × 30 × 1.10 (10% buffer)

    ALERTS:
        Projected daily > ₹250    → WARN  (83% of ₹300 limit)
        Projected daily > ₹270    → ALERT (90% of ₹300 limit)
        Projected monthly > ₹400  → WARN  (80% of ₹500 cap)
        Projected monthly > ₹450  → ALERT (90% of ₹500 cap)

    COST REDUCTION SUGGESTIONS:
        If projected > budget:
            1. Reduce pipeline frequency (6hr → 8hr → 12hr)
            2. Downgrade Tier-3 tasks to Tier-2 where quality sufficient
            3. Disable P3 tasks (dashboards, visualisations)
            4. Reduce MoA from 3 proposers to 2
            5. Skip non-critical ingestion sources
    """
    name = "CostProjectionAgent"
    domain = "infrastructure"
```

---

## Watchdog System

```
WATCHDOG HIERARCHY:

WatchdogAgent (separate process)
    └── Monitors:
        HealthCheckAgent    — heartbeat every 5 min
        LoopholeHunterAgent — heartbeat every 30 min
        LoggingAgent        — heartbeat every 10 min
        EventBus            — queue depth < 1000
        Main process        — memory < 8GB
        Disk space          — > 10GB free

    └── Recovery actions:
        Heartbeat missing   → restart agent (max 3 attempts)
        Queue overflow      → flush + alert
        Memory exceeded     → force GC + reduce cache
        Disk low            → purge old backups + alert

    └── Self-monitoring:
        WatchdogAgent writes heartbeat to /tmp/watchdog_alive
        Cron job checks file every 10 min
        If file stale → cron restarts WatchdogAgent process
```
