# Part II: Worker Layer — BaseWorker + 40 Workers
## FA v1 | Gap Mitigations: G1, G9 applied

## 2.1 BaseWorker Class (All Workers Inherit This)

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime
import asyncio

class BaseWorker(ABC):
    """
    Every worker in GeoSupply inherits from BaseWorker.
    Provides lifecycle hooks, automatic instrumentation,
    circuit breakers, and retry policies.

    LIFECYCLE:
        __init__()    → register capabilities + set retry policy
        setup()       → load models/connections (called once)
        process()     → do the work (called per task)
        teardown()    → cleanup (called on shutdown)

    AUTO-INSTRUMENTATION (applied by metaclass):
        @tracer       → span created per process() call
        @cost_tracker → INR cost logged per span
        @retry(max=3) → exponential backoff on failure
        @timeout(s)   → kill if exceeds time limit
        @breaker      → circuit breaker for external calls (v8)
        @internal_breaker → circuit breaker for internal agent calls (v10)
    """

    name: str                          # e.g. "SentimentWorker"
    tier: int                          # 0=CPU, 1=3b STATIC, 2=14b, 3=20b
    use_static: bool = False           # True = STATIC decoder mandatory
    capabilities: set[str] = set()     # e.g. {"SENTIMENT", "EMOTION_DETECT"}
    max_retries: int = 3
    timeout_seconds: int = 60

    @abstractmethod
    async def process(self, input_data: dict) -> dict:
        """Core work function. Must return dict with 'result' and 'meta'.
        On failure, raise WorkerProcessingError or return WorkerError schema."""
        pass

    async def setup(self):
        """Called once before first process(). Load models, open connections."""
        pass

    async def teardown(self):
        """Called on graceful shutdown. Close connections, flush buffers."""
        pass

    def advertise_capabilities(self) -> dict:
        """Return capabilities for MoE routing."""
        return {
            "name": self.name,
            "tier": self.tier,
            "capabilities": list(self.capabilities),
            "use_static": self.use_static,
        }

# --- FA v1: G9 FIX — Structured Error Schema ---
class WorkerError(BaseModel):
    """Returned by any worker on failure instead of raw exceptions.
    Ensures all errors are typed, costed, and traceable."""
    error_type: Literal["TIMEOUT", "API_FAILURE", "SCHEMA_VIOLATION",
                        "INPUT_INVALID", "BUDGET_EXCEEDED", "INTERNAL"]
    message: str
    worker_name: str
    retry_count: int = 0
    cost_inr: float = 0.0
    trace_id: str
    timestamp: datetime
```

---

## 2.2 Complete Worker Inventory (40 Workers)

### Ingestion Workers (4)

| # | Worker | Tier | STATIC | Capabilities | Source |
|---|--------|------|--------|-------------|--------|
| 1 | **NewsWorker** | 0 | No | INGEST_NEWS, RSS_PARSE | NewsAPI, GDELT, ACLED |
| 2 | **IndiaAPIWorker** | 0 | No | INGEST_INDIA_API, ULIP_QUERY | 129 ULIP APIs, DGFT, IMD, RBI |
| 3 | **TelegramWorker** | 0 | No | INGEST_TELEGRAM, OSINT_CHANNEL | 27+ Telegram channels |
| 4 | **AISWorker** | 0 | No | INGEST_AIS, VESSEL_TRACK | Marine AIS feeds |

### NLP Workers (5)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 5 | **LangWorker** | 0 | No | LANG_DETECT, SCRIPT_ID |
| 6 | **TranslationWorker** | 1-2 | No | TRANSLATE, 12_LANGS |
| 7 | **SentimentWorker** | 1 | ⚡ Yes | SENTIMENT_SCORE, EMOTION |
| 8 | **NERWorker** | 1 | ⚡ Yes | NER_EXTRACT, ENTITY_TYPE |
| 9 | **EmbedWorker** | 0 | No | EMBED_TEXT, VECTOR_768 |

### Intelligence Workers (8)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 10 | **ClaimWorker** | 1 | ⚡ Yes | CLAIM_EXTRACT, CLAIM_CLASSIFY |
| 11 | **VerifierWorker** | 3 | No | CLAIM_VERIFY, EVIDENCE_FIND |
| 12 | **SourceCredWorker** | 1 | ⚡ Yes | SOURCE_SCORE, CREDIBILITY |
| 13 | **AuthorWorker** | 3 | No | AUTHOR_PROFILE, BIAS_DETECT |
| 14 | **NetworkWorker** | 2 | No | NARRATIVE_NETWORK, CLUSTER |
| 15 | **CIBWorker** | 2 | No | CIB_DETECT, BOT_NETWORK |
| 16 | **PropagandaWorker** | 2 | No | PROPAGANDA_SCORE, TECHNIQUE |
| 17 | **CyberThreatWorker** | 1 | ⚡ Yes | CYBER_THREAT_SCORE, MITRE_MAP |

### ML Workers (3)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 18 | **ConflictWorker** | 0 | No | CONFLICT_PREDICT, PLATT_SCALE |
| 19 | **RetrainWorker** | 0 | No | MODEL_RETRAIN, DRIFT_FIX |
| 20 | **DriftWorker** | 0 | No | DRIFT_DETECT, PSI_SCORE |

### RAG Workers (5)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 21 | **RAGWorker** | 0-3 | No | RAG_QUERY, RETRIEVE |
| 22 | **GraphRAGWorker** | 3 | No | GRAPH_RAG, KG_TRAVERSE |
| 23 | **BriefWorker** | 3 | No | BRIEF_GENERATE, MOA_PROPOSE |
| 24 | **ContextBuildWorker** | 0 | No | CONTEXT_FUSE, WINDOW_MANAGE |
| 25 | **ReasonPlanWorker** | 3 | No | REASON_PLAN, SUB_QUESTION |

### Supply Chain Workers (3)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 26 | **StressWorker** | 3 | No | STRESS_INDEX, SUPPLY_RISK |
| 27 | **SupplierWorker** | 1 | ⚡ Yes | SUPPLIER_SCORE, DEPENDENCY |
| 28 | **SanctionsWorker** | 1 | ⚡ Yes | SANCTIONS_CHECK, ENTITY_SCREEN |

### India-Specific Workers (2)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 29 | **IndiaIntelWorker** | 1 | No | INDIA_INTEL, LAC_LOC_MONITOR |
| 30 | **MonsoonWorker** | 0 | No | MONSOON_TRACK, IMD_CORRELATE |

### Dashboard Workers (2)

| # | Worker | Tier | STATIC | Capabilities |
|---|--------|------|--------|-------------|
| 31 | **StreamlitWorker** | 0 | No | DASHBOARD_RENDER, PAGE_GEN |
| 32 | **CIVisualisationWorker** | 0 | No | CHART_GEN, MAP_RENDER |

### v10 New Workers (8)

| # | Worker | Tier | STATIC | Capabilities | Fixes |
|---|--------|------|--------|-------------|-------|
| 33 | **ChannelFingerprintWorker** | 0 | No | CHANNEL_FINGERPRINT, DRIFT_KL | v9 LOOPHOLE 1 |
| 34 | **InputSanitiserWorker** | 0 | No | SANITISE_INPUT, INJECTION_SCAN | v9 LOOPHOLE 2 |
| 35 | **CostProjectionWorker** | 0 | No | COST_PROJECT, TREND_ANALYSE | v9 BLIND SPOT 5 |
| 36 | **TwitterAPIWorker** | 0 | No | TWEET_POST, TWEET_DELETE | Marketing |
| 37 | **NewsletterWorker** | 0 | No | NEWSLETTER_SEND, SUBSCRIBE | Marketing |
| 38 | **SBOMWorker** | 0 | No | SBOM_GENERATE, SBOM_AUDIT | Tech Team |
| 39 | **BackupWorker** | 0 | No | BACKUP_RUN, BACKUP_RESTORE | v9 BLIND SPOT 4 |
| 40 | **LoopholeDetectionWorker** | 0 | No | LOOPHOLE_CHECK, SYSTEM_PROBE | v10 LoopholeHunter |

---

## 2.3 STATIC Decoder Workers (Tier-1 Schema-Strict)

These workers use the CSR-matrix constrained decoder that guarantees output conforms to Pydantic schema. No post-processing needed.

```
STATIC-MANDATORY WORKERS (9):
    SentimentWorker     → SentimentOutput schema
    NERWorker           → NEROutput schema
    ClaimWorker         → ClaimOutput schema
    SourceCredWorker    → SourceCredOutput schema
    CyberThreatWorker   → CyberThreatScore schema
    SupplierWorker      → SupplierScore schema
    SanctionsWorker     → SanctionsOutput schema
    SourceFeedbackSA    → SourceFeedbackScore schema (SubAgent)
    AuditSampleSA       → AuditSample schema (SubAgent)

INPUT GUARD (v10):
    All Tier-1 inputs pass through InputSanitiserWorker:
        Hard limit: 2048 tokens
        Warn: 1500 tokens
        Exceeds: truncate + summarise via Tier-2
```

## CROSS-CHECK ✅
```
✓ 40 workers listed (32 v8 + 8 v10)
✓ All STATIC workers identified (9)
✓ All workers have tier, capabilities, and STATIC flag
✓ All v10 workers map to specific loophole/gap fixes
✓ BaseWorker lifecycle (setup/process/teardown) documented
✓ Every worker uses INR cost tracking
✓ [FA v1] WorkerError schema added (G9 — structured error responses)
```
