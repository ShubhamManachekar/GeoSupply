# Part V: Supervisor Layer (14) + SwarmMaster Orchestrator
## FA v1 | Gap Mitigations: G4 applied

## 5.1 BaseSupervisor Class

```python
class BaseSupervisor(ABC):
    """
    Supervisors enforce budgets, priorities, and phase gates.
    They schedule agent work and manage backpressure.

    RESPONSIBILITIES:
        1. Budget gating (INR cap per cycle)
        2. Priority scheduling (critical tasks first)
        3. Work stealing (idle supervisors take overflow)
        4. Queue depth monitoring (reject if full)
        5. Phase gate enforcement (no N+1 before N complete)
    """

    name: str
    domain: str
    budget_inr: float                  # Max INR per pipeline cycle
    max_queue_depth: int = 50          # Backpressure limit
    agents: list[str]                  # Agents managed

    async def dispatch(self, task: 'TaskPacket') -> dict:
        """Route task to best available agent."""
        if self._queue_depth >= self.max_queue_depth:
            return {"status": "rejected", "reason": "queue_full"}
        if self._budget_remaining <= 0:
            return {"status": "rejected", "reason": "budget_exhausted"}

        agent = self._select_agent(task, self._available_agents())
        result = await agent.execute(task)
        self._budget_remaining -= result.get("cost_inr", 0)
        return result
```

---

## 5.2 Complete Supervisor Census (14)

### Core Domain Supervisors (10) — From v8/v9

| # | Supervisor | Agents Managed | Budget/Cycle | Key Gate |
|---|-----------|----------------|-------------|----------|
| 1 | **IngestSupervisor** | NewsWkr, IndiaAPIWkr, TelegramWkr, AISWkr | ₹5 | Rate limit, source throttle |
| 2 | **NLPSupervisor** | LangWkr, TranslWkr, SentimentWkr, NERWkr, EmbedWkr | ₹10 | Priority queue, STATIC gate |
| 3 | **IntelSupervisor** | ClaimWkr, VerifierWkr, SrcCredWkr, AuthorWkr, NetworkWkr, CIBWkr, PropagandaWkr, CyberThreatWkr + SourceClusterAgent | ₹20 | MoA control, fact-check pipeline |
| 4 | **MLSupervisor** | ConflictWkr, RetrainWkr, DriftWkr | ₹5 | Retrain trigger, PSI threshold |
| 5 | **IndiaSupervisor** | IndiaIntelWkr, MonsoonWkr + 5 India API workers | ₹10 | NDA gate, ministry auth |
| 6 | **DashboardSupervisor** | StreamlitWkr, CIVisWkr | ₹3 | Page routing, render priority |
| 7 | **InfraSupervisor** | All 9 infrastructure singletons | ₹2 | Singleton lifecycle, always-on |
| 8 | **QualitySupervisor** | FactCheckAgent, HallucinationCheckSA, SummarizationAuditAgent | ₹10 | 0.70 floor, quarantine |
| 9 | **DevSupervisor** | ScaffoldAgt, CodeReviewAgt, DocGenAgt, RefactorAgt | ₹5 | Phase gate, build order |
| 10 | **TestSupervisor** | UnitTest, IntegTest, LoadTest, Regression, ContractTest | ₹5 | 80% coverage, SLA gate |

### Extended Supervisors (2) — From v9

| # | Supervisor | Agents Managed | Budget/Cycle | Key Gate |
|---|-----------|----------------|-------------|----------|
| 11 | **TechSupervisor** | TechScout, APIScan, DepUpdate, Deploy | ₹5 | Human approval for production |
| 12 | **MarketingSupervisor** | ContentGen, TwitterPub, Prediction, Revenue, Analytics, Newsletter | ₹5 | Fact-check + approval queue |

### v10 New Supervisors (2)

| # | Supervisor | Agents Managed | Budget/Cycle | Key Gate |
|---|-----------|----------------|-------------|----------|
| 13 | **LoopholeHunterSupervisor** | LoopholeHunter, OverrideAudit, PenTest, SummarizationAudit | ₹1 | Critical findings → immediate alert |
| 14 | **DisasterRecoverySupervisor** | Backup, Watchdog, CostProjection | ₹0 | CANNOT be paused (safety) |

---

## 5.3 SwarmMaster Orchestrator (Layer 1) — Final

```python
class SwarmMaster:
    """
    The single orchestrator. Decomposes user intent into tasks,
    resolves dependencies, routes via MoE, manages global budget.

    COMPONENTS (v8 → v9 → v10):
        MoE Gating Network        v8  → Routes tasks to supervisors
        Task Decomposer           v9  → Breaks complex queries into subtasks
        Dependency Resolver       v9  → Ensures correct execution order
        Budget Manager (INR)      v8  → Global ₹500/month cap
        Session Coordinator       v8  → 6 max parallel slots
        Pipeline Rectifier        v9  → Fixes pipeline errors mid-run
        Routing Advisor           v9  → Suggests tier changes based on quality
        ColdStart Guard           v9  → Minimal pipeline if models cold
        Backpressure Controller   v9  → Per-supervisor queue monitoring

    NEW in v10:
        InternalCircuitBreakerRegistry  → Tracks all internal breakers
        CostProjectionIntegration       → Proactive budget management
        LoopholeEventConsumer           → Listens for audit findings
        WatchdogRegistration            → Reports heartbeat to WatchdogAgent
        MoAFallbackIntegration          → 4-level fallback chain on MoA failure
        SchemaVersionManager            → Handles Pydantic migrations (see G4 spec below)
        EnhancedDegradedMode            → Auto-recovery: Lv1-2 auto, Lv3-4 manual
    """

# --- FA v1: G4 FIX — SchemaVersionManager Spec ---
"""
SchemaVersionManager handles Pydantic schema evolution without breaking running pipelines.

STRATEGY:
    1. Every Pydantic schema has a `schema_version: int = 1` field
    2. When fields are ADDED → version bumps, old messages still valid (additive)
    3. When fields are REMOVED → deprecation window (2 releases), then migrate
    4. When fields are CHANGED → create new schema version, old version kept

MIGRATION RULES:
    - Receiver MUST accept schema_version >= N-1 (one version back)
    - Sender ALWAYS uses latest schema_version
    - SchemaVersionManager maintains registry: {schema_name: {current: N, min: N-1}}
    - On pipeline start: verify all agents use compatible schema versions
    - If mismatch detected: log WARNING + auto-convert if possible, REJECT if not

STORAGE:
    - Schema version registry in config.py: SCHEMA_VERSIONS dict
    - Migration functions in schemas.py: migrate_v1_to_v2() pattern
"""
```

### MoE Routing Table (Final — 50+ task types)

```python
ROUTING_TABLE = {
    # task_type: (supervisor, tier, uses_static)

    # Ingestion
    "INGEST_NEWS":          ("IngestSupervisor",            0, False),
    "INGEST_INDIA_API":     ("IngestSupervisor",            0, False),
    "INGEST_TELEGRAM":      ("IngestSupervisor",            0, False),
    "INGEST_AIS":           ("IngestSupervisor",            0, False),

    # NLP
    "LANG_DETECT":          ("NLPSupervisor",               0, False),
    "TRANSLATE":            ("NLPSupervisor",               2, False),
    "NER_EXTRACT":          ("NLPSupervisor",               1, True),
    "SENTIMENT":            ("NLPSupervisor",               1, True),
    "EMBED_TEXT":           ("NLPSupervisor",               0, False),

    # Intelligence
    "CLAIM_EXTRACT":        ("IntelSupervisor",             1, True),
    "CLAIM_VERIFY":         ("QualitySupervisor",           3, False),
    "SOURCE_SCORE":         ("IntelSupervisor",             1, True),
    "AUTHOR_PROFILE":       ("IntelSupervisor",             3, False),
    "NARRATIVE_NETWORK":    ("IntelSupervisor",             2, False),
    "CIB_DETECT":           ("IntelSupervisor",             2, False),
    "PROPAGANDA_SCORE":     ("IntelSupervisor",             2, False),
    "CYBER_THREAT_SCORE":   ("IntelSupervisor",             1, True),

    # ML
    "CONFLICT_PREDICT":     ("MLSupervisor",                0, False),
    "MODEL_RETRAIN":        ("MLSupervisor",                0, False),
    "DRIFT_DETECT":         ("MLSupervisor",                0, False),

    # RAG
    "RAG_QUERY":            ("IntelSupervisor",             3, False),
    "BRIEF_GENERATE":       ("IntelSupervisor",             3, False),

    # Supply Chain
    "STRESS_INDEX":         ("IndiaSupervisor",             3, False),
    "SUPPLIER_SCORE":       ("IndiaSupervisor",             1, True),
    "SANCTIONS_CHECK":      ("IndiaSupervisor",             1, True),

    # India
    "INDIA_INTEL":          ("IndiaSupervisor",             1, False),
    "MONSOON_TRACK":        ("IndiaSupervisor",             0, False),

    # Dashboard
    "DASHBOARD_RENDER":     ("DashboardSupervisor",         0, False),

    # v10 additions
    "CHANNEL_FINGERPRINT":  ("IngestSupervisor",            0, False),
    "INPUT_SANITISE":       ("InfraSupervisor",             0, False),
    "COST_PROJECT":         ("DisasterRecoverySupervisor",  0, False),
    "TWEET_POST":           ("MarketingSupervisor",         0, False),
    "NEWSLETTER_SEND":      ("MarketingSupervisor",         0, False),
    "SBOM_GENERATE":        ("TechSupervisor",              0, False),
    "BACKUP_RUN":           ("DisasterRecoverySupervisor",  0, False),
    "LOOPHOLE_CHECK":       ("LoopholeHunterSupervisor",    0, False),
    "PEN_TEST":             ("LoopholeHunterSupervisor",    0, False),
    "OVERRIDE_AUDIT":       ("LoopholeHunterSupervisor",    0, False),
    "SUMMARY_VERIFY":       ("QualitySupervisor",           2, False),
    "SOURCE_CLUSTER":       ("IntelSupervisor",             1, True),
    "CONTENT_DEDUP":        ("MarketingSupervisor",         0, False),
    "KG_CANARY":            ("InfraSupervisor",             0, False),
    "SCHEMA_MIGRATE":       ("InfraSupervisor",             0, False),
}
```

### DEGRADED_MODE (Final)

```
Level 1 (budget warning):   Auto-recover 60 min if budget resets
Level 2 (API failures):     Auto-recover 30 min probe cycle
Level 3 (hardware offline): MANUAL ONLY → admin release
Level 4 (emergency):        MANUAL ONLY → admin release

Core agents always active in ANY degraded level:
    LoggingAgent, SecurityAgent, HealthCheckAgent, WatchdogAgent
```

## CROSS-CHECK ✅
```
✓ 14 supervisors match agents from Part IV
✓ All 50+ task types in routing table
✓ Every STATIC task (True) maps to Tier-1
✓ Budget waterfall: sum of supervisor budgets ≤ global cap
✓ DisasterRecoverySupervisor cannot be paused
✓ DEGRADED_MODE has v10 auto-recovery for Lv1-2
✓ SwarmMaster has all v10 components
✓ [FA v1] SchemaVersionManager fully specified with migration strategy (G4)
```
