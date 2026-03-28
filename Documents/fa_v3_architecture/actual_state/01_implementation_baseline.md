<!-- markdownlint-disable MD004 MD022 MD032 MD058 MD060 -->

# Actual State: Implementation Baseline

Date: March 28, 2026 (Session 28)

## Verified Counts (Session 28 | 2026-03-28)
- Workers: 19 (phases 1-4 complete)
- Agents: 11 (unchanged)
- SubAgents: 13 (+3: OverridePatternSubAgent, MoAFallbackSubAgent, PenetrationTestSubAgent)
- Supervisors: 14 (+9: DR, ML, India, Dashboard, Dev, Test, Tech, Marketing, LoopholeHunter)
- Orchestrator: 1 (SwarmMaster at orchestrator/swarm_master.py)
- API Endpoints: 15 (Phase 9 started — FastAPI REST layer complete)
- Tests: 963 passing
- Schemas: 32 (unchanged)

## Implemented Workers (19)

### Ingestion Workers (Phase 2)
- `src/geosupply/workers/news_worker.py`
- `src/geosupply/workers/india_api_worker.py`
- `src/geosupply/workers/telegram_worker.py`
- `src/geosupply/workers/ais_worker.py`

### Infrastructure Workers (Phase 1)
- `src/geosupply/workers/input_sanitiser_worker.py`

### Event Intelligence (Phase 14)
- `src/geosupply/workers/event_extractor_worker.py`

### NLP Workers — Tier-1 STATIC (Phase 3)
- `src/geosupply/workers/claim_worker.py`
- `src/geosupply/workers/ner_worker.py`
- `src/geosupply/workers/sentiment_worker.py`
- `src/geosupply/workers/propaganda_worker.py`
- `src/geosupply/workers/translation_worker.py`

### Intel Workers — Phase 4
- `src/geosupply/workers/source_cred_worker.py` (Tier-1 STATIC)
- `src/geosupply/workers/cyber_threat_worker.py` (Tier-1 STATIC)
- `src/geosupply/workers/supplier_worker.py` (Tier-1 STATIC)
- `src/geosupply/workers/sanctions_worker.py` (Tier-1 STATIC)
- `src/geosupply/workers/network_worker.py` (Tier-2)
- `src/geosupply/workers/cib_worker.py` (Tier-2)
- `src/geosupply/workers/verifier_worker.py` (Tier-3)
- `src/geosupply/workers/author_worker.py` (Tier-3)

## Implemented Agents (11)

### Core / Infrastructure (Phase 0-1)
- `src/geosupply/agents/logging_agent.py`
- `src/geosupply/agents/security_agent.py`
- `src/geosupply/agents/health_check_agent.py`
- `src/geosupply/agents/swarm_manager_agent.py`
- `src/geosupply/agents/moe_router_agent.py`
- `src/geosupply/agents/budget_manager_agent.py`
- `src/geosupply/agents/route_manager_agent.py`

### Domain / Content
- `src/geosupply/agents/timeline_generator_agent.py`

### Phase 7: Knowledge Graph
- `src/geosupply/agents/knowledge_graph_agent.py` — with SQLite persistence (Session 21)

### Phase 6+: Quality Agents (Session 21)
- `src/geosupply/agents/fact_check_agent.py` — FACT_CHECK, CLAIM_VERIFY, EVIDENCE_SCORE, QUARANTINE_BRIEF
- `src/geosupply/agents/summarization_audit_agent.py` — SUMMARIZATION_AUDIT, DISTORTION_CHECK, BAND_VERIFY

## Implemented SubAgents (13)

### Phase 5 (original)
- `src/geosupply/subagents/nlp_pipeline_subagent.py`
- `src/geosupply/subagents/hallucination_check_subagent.py`
- `src/geosupply/subagents/audit_sample_subagent.py`
- `src/geosupply/subagents/source_feedback_subagent.py`
- `src/geosupply/subagents/rag_pipeline_subagent.py`

### Session 21 additions
- `src/geosupply/subagents/watchdog_subagent.py` — Rule 10; STUCK_BUSY/STUCK_ERROR/UNREACHABLE/RECOVERED alerts
- `src/geosupply/subagents/source_cluster_subagent.py` — coordinated source detection via domain/style/penalty clustering

### Session 22 additions
- `src/geosupply/subagents/graph_rag_subagent.py` — KG-enhanced RAG: entity extract → KG traversal → enrich query → vector search → merge/rerank → hallucination gate
- `src/geosupply/subagents/brief_synth_subagent.py` — 3-proposer MoA + 4-level aggregation fallback + SQLite audit invariant
- `src/geosupply/subagents/semantic_drift_monitor.py` — KL divergence per source channel; NORMAL/WARN/SUSPEND/SILENT alerts; publishes source.suspend / source.silent_alert events

### Session 28 additions
- `src/geosupply/subagents/override_pattern_subagent.py` — 4 pattern detectors (OVR-001 to OVR-004)
- `src/geosupply/subagents/moa_fallback_subagent.py` — SELECTED/MERGED/ESCALATE/BELOW_FLOOR logic
- `src/geosupply/subagents/penetration_test_subagent.py` — 5 security probes (PEN-001 to PEN-005)

## Implemented Supervisors (14) — Phase 6 + Sessions 22 + 28
- `src/geosupply/supervisors/ingestion_supervisor.py`
- `src/geosupply/supervisors/quality_supervisor.py`
- `src/geosupply/supervisors/nlp_supervisor.py` — with InputSanitiserWorker pre-gate (Session 21)
- `src/geosupply/supervisors/intel_supervisor.py`
- `src/geosupply/supervisors/infra_supervisor.py` — Session 22; cannot be paused; manages 9 infra singletons
- `src/geosupply/supervisors/disaster_recovery_supervisor.py` — Session 28; P0 cannot-be-paused; budget ₹2/cycle
- `src/geosupply/supervisors/ml_supervisor.py` — Session 28; budget ₹12/cycle
- `src/geosupply/supervisors/india_supervisor.py` — Session 28; budget ₹10/cycle
- `src/geosupply/supervisors/dashboard_supervisor.py` — Session 28; budget ₹3/cycle
- `src/geosupply/supervisors/dev_supervisor.py` — Session 28; budget ₹5/cycle
- `src/geosupply/supervisors/test_supervisor.py` — Session 28; budget ₹4/cycle
- `src/geosupply/supervisors/tech_supervisor.py` — Session 28; custom TECH_DB_CHECK budget gate
- `src/geosupply/supervisors/marketing_supervisor.py` — Session 28; budget ₹8/cycle
- `src/geosupply/supervisors/loophole_hunter_supervisor.py` — Session 28; cannot be paused; budget ₹5/cycle

## Implemented Orchestrator (1) — Session 28
- `src/geosupply/orchestrator/swarm_master.py` — SwarmMaster: 58-entry ROUTING_TABLE, SUPPLY_BRIEF_TEMPLATE (10 tasks), decompose(), execute_dag(), route(), run_supply_brief()

## Implemented REST API (Phase 9) — Session 28
- `src/geosupply/api/main.py` — FastAPI app with lifespan warmup, 8 routers
- `src/geosupply/api/schemas_api.py` — 13 HTTP envelope Pydantic v2 models
- `src/geosupply/api/dependencies.py` — singleton factories via lru_cache
- `src/geosupply/api/routers/health.py` — GET /health, GET /health/deep
- `src/geosupply/api/routers/tasks.py` — POST /tasks (202), GET /tasks/{id}
- `src/geosupply/api/routers/pipeline.py` — GET /pipeline/{id}
- `src/geosupply/api/routers/brief.py` — POST /brief (120s timeout)
- `src/geosupply/api/routers/workers.py` — GET /workers, /agents, /supervisors
- `src/geosupply/api/routers/budget.py` — GET /budget, GET /budget/history
- `src/geosupply/api/routers/kg.py` — GET /kg/query, POST /kg/update
- `src/geosupply/api/routers/audit.py` — GET /audit, GET /audit/run

## Gap Fixes Applied (Session 22)
| Gap | Before | After |
|-----|--------|-------|
| InfraSupervisor missing | watchdog.alert events had no consumer | InfraSupervisor subscribes + restarts stuck agents |
| SwarmMaster.decompose() missing | round-robin lane split only | decompose() + execute_dag() + route() + ROUTING_TABLE (21 entries) |
| GraphRAGSubAgent missing | KG unused in retrieval | KG traversal integrated into RAG pipeline |
| BriefSynthSubAgent missing | no MoA brief synthesis | 3-proposer MoA + 4-level fallback + SQLite audit invariant |
| SemanticDriftMonitor missing | no source drift detection | KL divergence weekly monitor with NORMAL/WARN/SUSPEND/SILENT |
| Schemas #30-32 missing | BriefProposal/DriftReport/DAGPlan undefined | Added to schemas.py + SCHEMA_VERSIONS in config.py |

## Gap Fixes Applied (Session 21)
| Gap | Before | After |
|-----|--------|-------|
| Rule 10 — no watchdog | no implementation | WatchdogSubAgent polls all agents |
| InputSanitiserWorker not wired | raw text to Tier-1 | NLPSupervisor pre-gate rejects injections |
| G3 half-open | no receive-side verify | BaseAgent.handle_event() + EventBus.verify_event() |
| KG data loss on restart | in-memory only | SQLite persist + load on setup(db_path) |
| FactCheckAgent missing | — | Implemented with HALLUCINATION_FLOOR enforcement |
| SourceClusterSubAgent missing | — | Implemented with Union-Find clustering |
| SummarizationAuditAgent missing | — | Implemented with severity band distortion check |

## Implemented Core Contracts
- Config and locked constants: `src/geosupply/config.py`
- Schemas: `src/geosupply/schemas.py` (32 schemas — up to DAGPlan #32)
- Base classes and decorators: `src/geosupply/core/*.py`
  - `base_agent.py`: handle_event() with G3 HMAC verification (Session 21)
  - `event_bus.py`: verify_event() public interface (Session 21)
- Audit CLI baseline: `src/geosupply/cli/audit.py`

## Test Coverage
- Total tests: 963 (all passing — unit + integration; +216 in Session 28)
- Integration tests: `tests/integration/test_pipeline_integration.py`, `tests/integration/test_api_integration.py`

## Schemas
- Total schemas: 32
  - #1-25: original schemas
  - #26: VerificationResult (VerifierWorker)
  - #27: AuthorProfile (AuthorWorker)
  - #28: WatchdogAlert (WatchdogSubAgent) — Session 21
  - #29: FactCheckResult (FactCheckAgent) — Session 21
  - #30: BriefProposal (BriefSynthSubAgent) — Session 22
  - #31: DriftReport (SemanticDriftMonitor) — Session 22
  - #32: DAGPlan (SwarmManagerAgent.decompose) — Session 22
- All schemas registered in ALL_SCHEMAS and SCHEMA_VERSIONS (audit-verified)

## Status Label
Foundation + ingestion + NLP + intel workers (19/19) + subagents (13/13) + supervisors (14/14)
+ KnowledgeGraphAgent with SQLite + FactCheckAgent + SummarizationAuditAgent
+ InfraSupervisor + SwarmMaster (dedicated orchestrator/swarm_master.py, 58-entry ROUTING_TABLE)
+ GraphRAGSubAgent + BriefSynthSubAgent + SemanticDriftMonitor
+ OverridePatternSubAgent + MoAFallbackSubAgent + PenetrationTestSubAgent
+ FastAPI REST API (15 endpoints, 8 routers)
+ integration tests + all G3 security fixes applied.

## Remaining Items (after Session 28)
1. Streamlit 12-page portal implementation under `src/geosupply/portal/` (Phase 9 remainder).
2. Phase 5 ML worker implementation (ConflictPredictWorker, StressScoreWorker) to back MLSupervisor with real worker logic.
3. Phase 15 FA v2 worker domains (Aviation, Disaster, Energy, Market, Convergence/Cascade).
4. KnowledgeGraphAgent full NetworkX + ChromaDB integration and degraded-mode controls in SwarmMaster (target-state backlog).

Session 28b note: Documentation trail synchronized and markdownlint warning set rectified for active handoff documents.
