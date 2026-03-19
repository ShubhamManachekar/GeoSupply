# Target State: Component Design Backlog — Session 21 Items (All Implemented in Session 22)
## FA v3 | Last Updated: 2026-03-19

> This document gives the complete design spec for each of the 5 high-priority items identified at Session 21 close. **All 5 items were implemented in Session 22.** All specs are grounded in FA v2 architecture (final_architecture/Part_V and Part_III) and the locked principles in `01_fa_v3_principles.md`.

---

## Item 1: InfraSupervisor (Layer 2)

### Source
FA v2 Part V §5.2 — Supervisor #7:
> `InfraSupervisor` manages all 9 infrastructure singleton agents. Budget ₹2/cycle. Key gate: singleton lifecycle, always-on. Subscribes to `watchdog.alert` topic and restarts stuck agents.

### Contract
- **Input task types**: INFRA_HEALTH, INFRA_LOG, INFRA_WATCHDOG, INFRA_RESTART, KG_CANARY, SCHEMA_MIGRATE, INPUT_SANITISE
- **Managed agents (from FA v2 Part V + v9_architecture/06_supervisor_layer.md)**:
  - LoggingAgent, HealthCheckAgent, SecurityAgent (infrastructure singletons)
  - FactCheckAgent (quality gate singleton)
  - BudgetManagerAgent, RouteManagerAgent, MoERouterAgent, SwarmManagerAgent (control plane)
  - KnowledgeGraphAgent (Phase 7 singleton)
- **Note**: v9_architecture spec lists: LoggingAgent, FactCheckAgent, HealthCheckAgent, SecurityAgent, AuditorAgent, SourceFeedbackAgent as the InfraSupervisor's core 6. The full 9-singleton set follows FA v2 Part V.
- **Budget**: ₹2/cycle (infra agents are Tier-0, CPU-only, near-zero cost)
- **Key gates**:
  - CANNOT be paused (same rule as DisasterRecoverySupervisor)
  - All 9 managed components must be IDLE or BUSY — never ERROR > 60s
  - Watchdog alert → restart attempt → log INFRA_RESTART event

### Watchdog Integration
```python
# On init, InfraSupervisor subscribes to watchdog.alert
self._event_bus.subscribe("watchdog.alert", self._on_watchdog_alert)

async def _on_watchdog_alert(self, event: Event) -> None:
    alert = WatchdogAlert(**event.payload)
    if alert.alert_type in ("STUCK_BUSY", "STUCK_ERROR"):
        agent = self._agent_registry.get(alert.agent_name)
        if agent:
            # Dispatch a recovery task to the stuck agent
            await agent.safe_execute({"action": "recover", "trace_id": alert.trace_id})
            logger.warning("InfraSupervisor: restart attempted for %s", alert.agent_name)
```

### Routing Table Entries (from FA v2)
```
INPUT_SANITISE  → InfraSupervisor (Tier-0, not STATIC)
KG_CANARY       → InfraSupervisor (Tier-0)
SCHEMA_MIGRATE  → InfraSupervisor (Tier-0)
INFRA_HEALTH    → InfraSupervisor → HealthCheckAgent
INFRA_LOG       → InfraSupervisor → LoggingAgent
```

### Implementation Checklist
- [x] `src/geosupply/supervisors/infra_supervisor.py`
- [x] `tests/unit/test_infra_supervisor.py`
- [x] Subscribe to `watchdog.alert` in `__init__`
- [x] `dispatch()` must not honor `pause()` (override pause guard)
- [x] INFRA_RESTART event logged via LoggingAgent on every restart attempt
- [x] Health report publishable on INFRA_HEALTH task

---

## Item 2: GraphRAGSubAgent (Layer 4)

### Source
FA v2 Part III §3.2 — RAGPipelineSubAgent Step 2 (Retrieve) + KG integration:
> Step 2: `RetrieveSubAgent` (×N parallel) — queries ChromaDB. GraphRAG variant enhances step 2 by first traversing the KnowledgeGraphAgent entity neighborhood to build an entity-enriched query, then combining KG context with vector search results.

### Design
```
Pipeline:
  Step 1: extract_entities   → parse entity list from query (NER lightweight)
  Step 2: kg_traversal       → KnowledgeGraphAgent.execute(KG_QUERY, entity=X)
                                 for each entity (parallel for multi-entity queries)
  Step 3: enrich_query       → merge entity neighborhood into query string
  Step 4: vector_search      → ChromaDB query with enriched query
  Step 5: merge_and_rerank   → combine KG triples + vector results, deduplicate
  Step 6: hallucination_gate → confidence check ≥ HALLUCINATION_FLOOR

Parallel steps: {kg_traversal} (for multi-entity)
```

### Input / Output Contract
```python
# Input
{
    "query": str,                    # original retrieval query
    "entities": list[str],           # optional pre-extracted entity names
    "top_k": int,                    # how many docs to return (default 5)
    "kg_depth": int,                 # KG traversal hops (default 1)
    "trace_id": str,
}

# Output
{
    "result": {
        "context_chunks": list[dict],  # text + source + relevance_score
        "kg_triples": list[dict],      # source/relation/target from KG traversal
        "entity_count": int,
        "confidence": float,           # aggregate faithfulness score
        "retrieval_method": str,       # "kg_enhanced" | "vector_only" | "kg_only"
    },
    "meta": {"subagent": ..., "cost_inr": ...}
}
```

### Cost Model
- KG traversal: ₹0.0 (no LLM, in-memory dict)
- ChromaDB vector search: ₹0.0 (local)
- Total: ₹0.0 per query (Tier-0 only)

### Implementation Checklist
- [x] `src/geosupply/subagents/graph_rag_subagent.py`
- [x] `tests/unit/test_graph_rag_subagent.py`
- [x] KnowledgeGraphAgent injected (or stub-callable) in `__init__`
- [x] ChromaDB client injected (or mocked in tests)
- [x] HALLUCINATION_FLOOR check on merged confidence
- [x] Graceful fallback: if KG has no entity → vector-only path

---

## Item 3: BriefSynthSubAgent (Layer 4)

### Source
FA v2 Part III §3.2 — BriefSynthSubAgent:
> 3-proposer + 1-aggregator Mixture-of-Agents. All 3 proposals saved to SQLite BEFORE aggregation. 4-level MoA fallback chain. Internal circuit breaker timeout: 60s.

### MoA Architecture
```
Step 1: propose_×3 (parallel)
    Proposer A: BriefWorkerA (Tier-3, GPT-OSS:20b) — full evidence
    Proposer B: BriefWorkerB (Tier-2, qwen2.5:14b) — concise
    Proposer C: BriefWorkerC (Tier-1, llama3.2:3b) — minimal/bullet

Step 2: save_proposals
    SQLite: INSERT all 3 proposals before any aggregation (audit invariant)

Step 3: aggregate
    Level 0 (primary):   GPT-OSS:20b aggregation
    Level 1 (fallback):  Groq llama-3.3-70b aggregation
    Level 2 (scoring):   MOA_SCORING_WEIGHTS = {factcheck:0.4, source_cred:0.3, evidence_ratio:0.3}
                         Select proposal with highest weighted score
    Level 3 (manual):    Return all 3 to admin queue for human selection

Step 4: hallucination_gate
    Confidence ≥ HALLUCINATION_FLOOR (0.70) required to proceed
```

### Key Config References
```python
# config.py (already present)
MOA_SCORING_WEIGHTS = {"factcheck_score": 0.4, "source_credibility_avg": 0.3, "claim_evidence_ratio": 0.3}
MOA_MERGE_THRESHOLD = 0.05    # if top 2 within 0.05, merge
MOA_ESCALATE_THRESHOLD = 0.50 # below this → Level 3 manual
INTERNAL_BREAKER_TIMEOUT_MAP = {"BriefSynthSubAgent": 60}
INTERNAL_BREAKER_MAX_FAILURES = 3
```

### Input / Output Contract
```python
# Input
{
    "context_chunks": list[dict],   # from GraphRAGSubAgent
    "claim_text": str,
    "risk_scores": dict,            # from NLP + Intel workers
    "source_credibility": float,
    "budget_inr": float,            # max spend for this brief
    "trace_id": str,
}

# Output
{
    "result": {
        "brief_text": str,
        "confidence": float,
        "aggregation_level_used": int,   # 0-3
        "proposer_count": int,
        "proposal_ids": list[str],       # SQLite row IDs for audit
        "cost_breakdown": dict,
    },
    "meta": {"subagent": ..., "cost_inr": float}
}
```

### Implementation Checklist
- [x] `src/geosupply/subagents/brief_synth_subagent.py`
- [x] `tests/unit/test_brief_synth_subagent.py`
- [x] SQLite `briefs` table: `(id, trace_id, proposal_text, confidence, proposer_tier, created_at)`
- [x] All 3 proposals persisted BEFORE aggregation (audit invariant)
- [x] 4-level MoA fallback with level tracking
- [x] Internal circuit breaker (timeout=60s, max_failures=3)
- [x] HALLUCINATION_FLOOR enforcement at Step 4

---

## Item 4: SwarmMaster.decompose() + TaskPacket DAG Routing (Layer 1)

### Source
FA v2 Part V §5.3 — SwarmMaster:
> Task Decomposer: Breaks complex queries into subtasks. Dependency Resolver: Ensures correct execution order. `TaskPacket` already has `dependencies: list[str]` field.

### Current Gaps
1. `SwarmManagerAgent.execute()` does only round-robin lane splitting — no decompose logic
2. No DAG dependency resolution
3. No routing from SwarmMaster to named supervisors
4. No `decompose()` public method
5. No `execute_dag()` that respects `TaskPacket.dependencies`

### Design

#### `SwarmManagerAgent` additions
```python
async def decompose(self, compound_task: dict) -> list[TaskPacket]:
    """
    Break a compound task into atomic TaskPackets with dependency edges.

    Decomposition rules:
      - INGEST + NLP + INTEL: always sequential (INTEL depends on NLP depends on INGEST)
      - Multiple INTEL subtasks: parallel (no inter-dependency)
      - QA check: always after INTEL
      - BRIEF_GENERATE: after QA

    Returns ordered list with TaskPacket.dependencies populated.
    """

async def execute_dag(
    self,
    tasks: list[TaskPacket],
    supervisor_registry: dict[str, BaseSupervisor],
) -> dict:
    """
    Execute a list of TaskPackets in dependency order.

    Algorithm:
      1. Topological sort by TaskPacket.dependencies
      2. Execute tasks with no pending dependencies in parallel (asyncio.gather)
      3. Mark completed, unblock dependents
      4. Return results keyed by task_id
    """
```

#### MoE Routing Integration
```python
# Route a TaskPacket to its supervisor based on ROUTING_TABLE
async def route(
    self,
    task: TaskPacket,
    supervisor_registry: dict[str, BaseSupervisor],
) -> dict:
    supervisor_name, tier, uses_static = ROUTING_TABLE[task.task_type]
    supervisor = supervisor_registry[supervisor_name]
    return await supervisor.dispatch(task)
```

#### ROUTING_TABLE to implement
From FA v2 Part V, 50+ entries. Priority subset for MVP:
```python
ROUTING_TABLE = {
    "INGEST_NEWS":       ("IngestionSupervisor",  0, False),
    "NLP_SENTIMENT":     ("NLPSupervisor",         1, True),
    "NLP_NER":           ("NLPSupervisor",         1, True),
    "NLP_CLAIM":         ("NLPSupervisor",         1, True),
    "CLAIM_VERIFY":      ("QualitySupervisor",     3, False),
    "SOURCE_SCORE":      ("IntelSupervisor",       1, True),
    "NARRATIVE_NETWORK": ("IntelSupervisor",       2, False),
    "RAG_QUERY":         ("IntelSupervisor",       3, False),
    "BRIEF_GENERATE":    ("IntelSupervisor",       3, False),
    "SUPPLIER_SCORE":    ("IntelSupervisor",       1, True),
    "SANCTIONS_CHECK":   ("IntelSupervisor",       1, True),
    "INPUT_SANITISE":    ("InfraSupervisor",       0, False),
    "KG_CANARY":         ("InfraSupervisor",       0, False),
    "INFRA_HEALTH":      ("InfraSupervisor",       0, False),
    "BACKUP_RUN":        ("DisasterRecoverySupervisor", 0, False),
    "COST_PROJECT":      ("DisasterRecoverySupervisor", 0, False),
}
```

### Standard Decomposition Template (SUPPLY_BRIEF)
```
SUPPLY_BRIEF compound task decomposes to:
  T1: INGEST_NEWS           (no deps)
  T2: INGEST_INDIA_API      (no deps)  ← parallel with T1
  T3: NLP_NER               (deps: T1, T2)
  T4: NLP_SENTIMENT         (deps: T1, T2)   ← parallel with T3
  T5: NLP_CLAIM             (deps: T1, T2)   ← parallel with T3, T4
  T6: SOURCE_SCORE          (deps: T3, T4, T5)
  T7: CLAIM_VERIFY          (deps: T5)       ← parallel with T6
  T8: NARRATIVE_NETWORK     (deps: T3, T6)   ← parallel with T7
  T9: RAG_QUERY             (deps: T3, T5, T6, T7)
  T10: BRIEF_GENERATE       (deps: T8, T9)
```

### Implementation Checklist
- [x] Add `decompose()` to `SwarmManagerAgent`
- [x] Add `execute_dag()` with topological sort
- [x] Add `route()` with ROUTING_TABLE lookup
- [x] `tests/unit/test_swarm_manager_agent.py` — extend with DAG tests
- [x] SUPPLY_BRIEF decomposition template as class constant
- [x] Budget check before each `supervisor.dispatch()` call

---

## Item 5: SemanticDriftMonitor (Layer 4 SubAgent)

### Source
FA v2 Part III §3.2 — v10 New SubAgents listing (Quality Assurance group):
> `SemanticDriftMonitor`. Schedule: Weekly. Method: KL divergence on document embeddings per source. Alert: If KL > 0.30 on any source → flag for review.

### Config References (already in config.py)
```python
CHANNEL_BASELINE_MIN_MESSAGES = 100    # Baseline requires ≥100 messages
CHANNEL_KL_WARN_THRESHOLD = 0.30       # Flag for review
CHANNEL_KL_SUSPEND_THRESHOLD = 0.60   # Auto-suspend source
CHANNEL_SILENT_ALERT_DAYS = 7         # Alert if no messages for 7 days
```

### Design
```
Pipeline:
  Step 1: load_baselines     → retrieve ChannelFingerprint baselines per channel
  Step 2: compute_current    → build n-gram distribution from recent messages
  Step 3: kl_divergence      → compute KL(current || baseline) per channel
  Step 4: classify_drift     → NORMAL / WARN / SUSPEND / SILENT
  Step 5: emit_alerts        → publish drift events to EventBus

Parallel steps: {compute_current, kl_divergence} for multiple channels
```

### KL Divergence Implementation
```python
import math

def kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """
    KL(P || Q) — measure how much P has drifted from baseline Q.
    Smoothing: add epsilon=1e-10 to avoid log(0).
    """
    vocab = set(p) | set(q)
    eps = 1e-10
    return sum(
        p.get(w, eps) * math.log((p.get(w, eps)) / (q.get(w, eps) + eps))
        for w in vocab
        if p.get(w, eps) > 0
    )
```

### Input / Output Contract
```python
# Input
{
    "channels": list[dict],  # each: {channel_id, recent_messages: list[str], baseline_ngrams: dict}
    "trace_id": str,
}

# Output
{
    "result": {
        "drift_report": list[dict],  # per channel: {channel_id, kl_score, alert_level, action}
        "total_channels": int,
        "warn_count": int,
        "suspend_count": int,
        "silent_count": int,
    },
    "meta": {"subagent": ..., "cost_inr": 0.0}
}
```

### Alert Levels
```
KL < 0.30                    → NORMAL (no action)
0.30 ≤ KL < 0.60             → WARN (flag for human review)
KL ≥ 0.60                    → SUSPEND (auto-suspend source, alert admin)
no messages in 7 days        → SILENT (alert admin — source may be compromised)
```

### Implementation Checklist
- [x] `src/geosupply/subagents/semantic_drift_monitor.py`
- [x] `tests/unit/test_semantic_drift_monitor.py`
- [x] `kl_divergence()` with epsilon smoothing (pure Python, no LLM)
- [x] Uses `ChannelFingerprint` schema (#19) for baseline storage reference
- [x] SUSPEND action publishes `Event(topic="source.suspend", ...)` to EventBus
- [x] SILENT action publishes `Event(topic="source.silent_alert", ...)` to EventBus
- [x] Schedule: runs as part of DisasterRecoverySupervisor weekly cycle
- [x] Baseline validation: requires `CHANNEL_BASELINE_MIN_MESSAGES` before checking

---

## Priority Order for Implementation

| Priority | Item | Reason |
|----------|------|--------|
| P0 | InfraSupervisor | Watchdog alerts go nowhere without it; safety-critical |
| P0 | SwarmMaster.decompose() + DAG routing | No end-to-end pipeline without task routing |
| P1 | GraphRAGSubAgent | Unlocks KnowledgeGraphAgent usefulness |
| P1 | BriefSynthSubAgent | Completes the RAG pipeline to final output |
| P2 | SemanticDriftMonitor | Important for source quality but not blocking pipeline |

## Dependencies Graph
```
InfraSupervisor ← WatchdogSubAgent (already done)
GraphRAGSubAgent ← KnowledgeGraphAgent (SQLite done) + ChromaDB
BriefSynthSubAgent ← GraphRAGSubAgent + SQLite brief store
SwarmMaster DAG ← All supervisors (currently 5/14)
SemanticDriftMonitor ← ChannelFingerprint baselines (schema exists)
```

## New Schemas Required
| # | Schema | Used by |
|---|--------|---------|
| #30 | `BriefProposal` | BriefSynthSubAgent (3 proposals saved before aggregation) |
| #31 | `DriftReport` | SemanticDriftMonitor output |
| #32 | `DAGPlan` | SwarmMaster.decompose() output |
