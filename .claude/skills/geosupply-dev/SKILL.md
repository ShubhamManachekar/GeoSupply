---
name: geosupply-dev
description: GeoSupply AI development conventions, architecture rules, and code generation templates aligned to FA v3 canonical docs and current implementation state.
---

# GeoSupply AI Development Skill

## Architecture Context

GeoSupply AI is an India-centric geopolitical supply chain intelligence platform with FA v3 documentation governance. Use `Documents/fa_v3_architecture/actual_state/` for implementation truth and `Documents/fa_v3_architecture/target_state/` for intended architecture.

## Current Baseline (Session 22 | 2026-03-19)

| Layer | Component | Count |
|-------|-----------|-------|
| Workers | Ingestion (4) + Infra (1) + Event (1) + NLP (5) + Intel (8) | **19** |
| Agents | Logging, Security, HealthCheck, Timeline, Swarm, MoE, Budget, Route, KnowledgeGraph, FactCheck, SummarizationAudit | **11** |
| SubAgents | NLPPipeline, HallucinationCheck, AuditSample, SourceFeedback, RAGPipeline, Watchdog, SourceCluster, **GraphRAG**, **BriefSynth**, **SemanticDriftMonitor** | **10** |
| Supervisors | Ingestion, Quality, NLP (+ InputSanitiser pre-gate), Intel, **Infra** | **5** |
| Orchestrator | SwarmManagerAgent has decompose()/execute_dag()/route() — no dedicated class yet | 0 |

Tests: **747 passing** | Schemas: **32** (up to DAGPlan #32)

## Gap Fixes Applied (Session 21)
| Gap | Fix | Location |
|-----|-----|----------|
| Rule 10 — no watchdog | `WatchdogSubAgent` polls agent.state, escalates STUCK_BUSY/ERROR/UNREACHABLE | `subagents/watchdog_subagent.py` |
| InputSanitiserWorker not wired | `NLPSupervisor.dispatch()` runs sanitiser pre-gate on `text` field | `supervisors/nlp_supervisor.py` |
| G3 half-open | `EventBus.verify_event()` public + `BaseAgent.handle_event(event, event_bus)` | `core/event_bus.py`, `core/base_agent.py` |
| KG restart data loss | `KnowledgeGraphAgent` SQLite persistence via `setup(db_path)` + `_persist_edge()` + `_load_from_db()` | `agents/knowledge_graph_agent.py` |
| FactCheckAgent missing | `FactCheckAgent` — FACT_CHECK, CLAIM_VERIFY, EVIDENCE_SCORE, QUARANTINE_BRIEF | `agents/fact_check_agent.py` |
| SourceClusterSubAgent missing | `SourceClusterSubAgent` — domain/style/penalty clustering | `subagents/source_cluster_subagent.py` |
| SummarizationAuditAgent missing | `SummarizationAuditAgent` — severity band distortion check | `agents/summarization_audit_agent.py` |

## Gap Fixes Applied (Session 22)
| Gap | Fix | Location |
|-----|-----|----------|
| InfraSupervisor missing | `InfraSupervisor` — watchdog.alert consumer, cannot be paused, 9 infra singletons | `supervisors/infra_supervisor.py` |
| SwarmMaster.decompose() missing | `decompose()` + `execute_dag()` + `route()` + ROUTING_TABLE (21 entries) + SUPPLY_BRIEF template | `agents/swarm_manager_agent.py` |
| GraphRAGSubAgent missing | KG traversal + vector search + merge/rerank + hallucination gate | `subagents/graph_rag_subagent.py` |
| BriefSynthSubAgent missing | 3-proposer MoA + 4-level fallback + SQLite audit invariant | `subagents/brief_synth_subagent.py` |
| SemanticDriftMonitor missing | KL divergence per source channel; NORMAL/WARN/SUSPEND/SILENT | `subagents/semantic_drift_monitor.py` |

**Test count**: 747 passing. Integration tests in `tests/integration/`.
Dynamic audit is the source of count truth: `python -m geosupply.cli.audit --level strict`.

### Phases Complete (Session 22)
- ✅ Phase 0: Foundation (config, 32 schemas, base classes + G3 BaseAgent.handle_event)
- ✅ Phase 1: Infrastructure (LoggingAgent, SecurityAgent, HealthCheckAgent, EventBus.verify_event)
- ✅ Phase 2: Data Ingestion (NewsWorker, IndiaAPIWorker, TelegramWorker, AISWorker + InputSanitiser wired in NLPSupervisor)
- ✅ Phase 3: NLP Workers (Claim, NER, Sentiment, Propaganda, Translation)
- ✅ Phase 4: Intel Workers (all 8/8)
- 🟡 Phase 5-6: SubAgents (10/13) + Supervisors (5/14)
- 🟡 Phase 7: KnowledgeGraphAgent + G5 dedup + SQLite persistence (NetworkX/ChromaDB planned)
- 🟡 Phase 8: SwarmMaster DAG routing (in SwarmManagerAgent, not dedicated orchestrator class)
- ✅ Phase 14: Audit/QA tooling

### Remaining P0 Items (blocks end-to-end pipeline)
1. **Dedicated Orchestrator class** — SwarmManagerAgent has the methods but no standalone Layer 1 orchestrator.
2. **9 remaining supervisors** — MLSupervisor, IndiaSupervisor, DashboardSupervisor, DevSupervisor, TestSupervisor, TechSupervisor, MarketingSupervisor, LoopholeHunterSupervisor, DisasterRecoverySupervisor.

### Remaining P1 Items
3. **3 remaining subagents** — OverridePatternSubAgent, MoAFallbackSubAgent, PenetrationTestSubAgent.
4. **End-to-end integration test** — full SUPPLY_BRIEF pipeline via execute_dag.

## Locked Rules (NEVER Override)

1. **DAG + Pydantic v2** — All inter-component communication uses typed `AgentMessage` schema
2. **3-tier LLM routing**: Tier 1 (3b + STATIC) → Tier 2 (14b) → Tier 3 (20b)
3. **No lateral communication** — Workers/Supervisors NEVER talk to peers directly
4. **Single-writer** for state (Tier 0 authority)
5. **Infrastructure OFF critical path**
6. **XGBoost ISOLATED from LLMs**
7. **HALLUCINATION_FLOOR = 0.70** (LOCKED)
8. **All costs in INR** — never USD
9. **TRUST NOTHING** — validate every data flow
10. **Every agent has a watchdog**
16. **ZERO MOCKS** — All tests must exercise REAL logic, NEVER use placeholder/mock/fake logic
17. Run phase-end audits BEFORE closing any phase gate
18. NEVER hardcode component counts — use dynamic discovery
19. Every new Worker/Agent must be discoverable by the audit system automatically
20. Every schema added to ALL_SCHEMAS MUST have a matching SCHEMA_VERSIONS entry
21. BROKEN CHAIN CHECK — all core imports must resolve cleanly
22. LOGIC LOOPHOLE CHECK — `process()` overriden, valid MRO
24. PRACTICAL GATE — Full pytest suite must pass during audit

## Code Conventions

```python
# Python 3.10+, type hints everywhere
# Pydantic v2 for ALL schemas
# async/await for ALL I/O operations
# @breaker for external API calls
# @internal_breaker for Tier-3+ agent calls
# SecurityAgent.get_key() for ALL API keys — never hardcode
# Every process() must track cost_inr in meta
```

## Architecture Design References (Implemented in Session 22)

### SwarmMaster ROUTING_TABLE (MVP subset)
```python
# task_type → (supervisor_name, tier, uses_static)
ROUTING_TABLE = {
    "INGEST_NEWS":       ("IngestionSupervisor",          0, False),
    "NLP_SENTIMENT":     ("NLPSupervisor",                1, True),
    "NLP_NER":           ("NLPSupervisor",                1, True),
    "NLP_CLAIM":         ("NLPSupervisor",                1, True),
    "CLAIM_VERIFY":      ("QualitySupervisor",            3, False),
    "SOURCE_SCORE":      ("IntelSupervisor",              1, True),
    "NARRATIVE_NETWORK": ("IntelSupervisor",              2, False),
    "RAG_QUERY":         ("IntelSupervisor",              3, False),
    "BRIEF_GENERATE":    ("IntelSupervisor",              3, False),
    "INPUT_SANITISE":    ("InfraSupervisor",              0, False),
    "KG_CANARY":         ("InfraSupervisor",              0, False),
    "INFRA_HEALTH":      ("InfraSupervisor",              0, False),
    "BACKUP_RUN":        ("DisasterRecoverySupervisor",   0, False),
    "COST_PROJECT":      ("DisasterRecoverySupervisor",   0, False),
}
```

### SUPPLY_BRIEF DAG Decomposition Template
```
T1: INGEST_NEWS         (deps: [])
T2: INGEST_INDIA_API    (deps: [])              ← parallel with T1
T3: NLP_NER             (deps: [T1, T2])
T4: NLP_SENTIMENT       (deps: [T1, T2])        ← parallel with T3
T5: NLP_CLAIM           (deps: [T1, T2])        ← parallel with T3, T4
T6: SOURCE_SCORE        (deps: [T3, T4, T5])
T7: CLAIM_VERIFY        (deps: [T5])            ← parallel with T6
T8: NARRATIVE_NETWORK   (deps: [T3, T6])        ← parallel with T7
T9: RAG_QUERY           (deps: [T3, T5, T6, T7])
T10: BRIEF_GENERATE     (deps: [T8, T9])
```

### BriefSynthSubAgent MoA Levels
```
Level 0: GPT-OSS:20b full aggregation (primary) — INTERNAL_BREAKER_TIMEOUT=60s
Level 1: Groq llama-3.3-70b aggregation (cloud fallback)
Level 2: MOA_SCORING_WEIGHTS = {factcheck:0.4, source_cred:0.3, evidence_ratio:0.3}
Level 3: Manual — return all 3 proposals to admin queue
MOA_MERGE_THRESHOLD = 0.05  (if top 2 within 0.05, merge)
MOA_ESCALATE_THRESHOLD = 0.50  (below this → Level 3)
SQLite invariant: ALL 3 proposals saved BEFORE aggregation begins
```

### InfraSupervisor — Key Constraint
```
CANNOT be paused (override BaseSupervisor.pause() to raise or no-op)
Subscribes to "watchdog.alert" on EventBus at __init__
On STUCK_BUSY / STUCK_ERROR alert → safe_execute({"action":"recover"}) on agent
On UNREACHABLE alert → log INFRA_RESTART + alert admin via LoggingAgent
```

## Banned Patterns (Learned from Phase 0+1)

```python
# ❌ BANNED: Python 3.14 deprecated
datetime.utcnow()

# ✅ REQUIRED: timezone-aware
from datetime import datetime, timezone
datetime.now(timezone.utc)

# ❌ BANNED: bare exception swallowing
except Exception:
    pass

# ✅ REQUIRED: log + return structured error
except Exception as exc:
    logger.error("...: %s", exc)
    return WorkerError(error_type="INTERNAL", message=str(exc), ...)

# ❌ BANNED: hardcoded API keys
api_key = "sk-..."

# ✅ REQUIRED: SecurityAgent vault
key = security_agent.get_key("groq")
```

## Module Creation Checklist

When creating any new module:

1. [ ] Inherits correct base class (BaseWorker/BaseSubAgent/BaseAgent/BaseSupervisor)
2. [ ] Has `name`, `tier`, `capabilities` defined
3. [ ] Uses `async def process()` / `async def run()` / `async def execute()`
4. [ ] Returns structured `dict` with `result` and `meta` (including `cost_inr`)
5. [ ] On failure, returns `WorkerError` schema (schema #23)
6. [ ] Has `setup()` and `teardown()` lifecycle hooks
7. [ ] Has corresponding test in `tests/unit/`
8. [ ] Tests use REAL logic — no AsyncMock for the component under test
9. [ ] Type hints on all function signatures
10. [ ] Docstring with class purpose and data flow
11. [ ] All datetime calls use `datetime.now(timezone.utc)` — never `utcnow()`
12. [ ] Agent `execute()` handles unknown actions with error dict
13. [ ] If `__init__()` is overridden, call `super().__init__()` for forward compatibility
14. [ ] Control-plane agents must defensively parse malformed payload fields (no uncaught `TypeError`/`ValueError`)

## Testing Rules (Learned from Phase 1)

### Philosophy: "Not Mock, Logically"
- Test the **real component** — only mock external dependencies (APIs, DBs in other services)
- Use **temp files** for SQLite tests (`Path(tempfile.mktemp(suffix=".db"))`)
- Use **env patching** for API key tests (`patch.dict(os.environ, {...})`)
- Use **backdated timestamps** for rotation/expiry tests (not time mocking)
- Inject **real errors** (drop tables, corrupt state) — don't just mock exceptions

### Coverage Targets
- Every file **must** be ≥ 85% (project gate: 80%)
- Run with `-W error::DeprecationWarning` to catch deprecations as failures
- Coverage command: `$env:PYTHONPATH="src"; python -m pytest tests/unit/ --cov=src/geosupply --cov-report=term-missing -W error::DeprecationWarning`

### Test Structure Pattern
```python
@pytest.fixture
async def agent():
    """Fixture with real setup/teardown — not a mock."""
    a = MyAgent(db_path=Path(tempfile.mktemp(suffix=".db")))
    await a.setup()
    yield a
    await a.teardown()

class TestHappyPath:
    """Normal operations with real data."""

class TestErrorPaths:
    """Error injection — real DB errors, invalid input, budget exhaustion."""

class TestEdgeCases:
    """Boundary conditions — empty input, max limits, zero budget."""

class TestExecuteContract:
    """BaseAgent.execute() for each action."""
```

### Cross-Phase Audit Checklist
After completing any phase, run these checks:
1. [ ] **Connectivity**: All imports resolve, no circular deps
2. [ ] **Logic Gaps**: Every error path returns structured error, agents recover to IDLE
3. [ ] **Breakages**: Class hierarchies match architecture, schema counts match
4. [ ] **Oversights**: All claimed features actually exist in code
5. [ ] **Hallucinations**: DEVELOPMENT_TRAIL claims match actual implementation
6. [ ] **Integration**: Full pipeline flow works end-to-end

## FA v1 Gap Mitigations (Quick Reference)

| Gap | Issue | Where Implemented |
|-----|-------|-------------------|
| G1 | SubAgent lifecycle hooks missing | `base_subagent.py` — `setup()`, `teardown()` |
| G2 | Agent state Machine has no guards | `base_agent.py` — `VALID_STATE_TRANSITIONS` |
| G3 | EventBus messages unsigned | `event_bus.py` — HMAC-SHA256 signing |
| G4 | Schema versioning undefined | `schemas.py` — `schema_version=1` on all 25 |
| G5 | KG dedup key missing | `schemas.py` — `KnowledgeUpdateRequest.dedup_key` |
| G6 | Channel fingerprint baseline timing | `schemas.py` — `ChannelFingerprint.status` Literals |
| G7 | WebSocket JWT scopes undefined | `config.py` — `WS_JWT_SCOPES` |
| G8 | MoA Level 2 scoring criteria missing | `config.py` — `MOA_SCORING_WEIGHTS` (sum=1.0) |
| G9 | WorkerError schema didn't exist | `schemas.py` — schema #23 with 6 error types |
| G10 | Test fixtures not standardised | `tests/fixtures/` — factories + InMemoryEventBus |

## Templates

See the `templates/` directory for ready-to-use code templates:
- `worker-template.md` — BaseWorker implementation pattern
- `agent-template.md` — BaseAgent with state machine
- `subagent-template.md` — BaseSubAgent pipeline pattern
- `testing-patterns.md` — Test fixture and async test patterns
