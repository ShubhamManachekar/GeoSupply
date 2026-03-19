# Actual State: Implementation Baseline

Date: March 19, 2026 (Session 21)

## Code-Verified Counts — Session 22 (2026-03-19)
- Workers implemented: 21
- Agents implemented: 11 (SwarmManagerAgent now has decompose() / execute_dag() / route() + ROUTING_TABLE)
- Subagents implemented: 10 (GraphRAGSubAgent, BriefSynthSubAgent, SemanticDriftMonitor added)
- Supervisors implemented: 5 (InfraSupervisor added — watchdog.alert consumer)
- Orchestrator implementations: 0 (SwarmMaster DAG routing in SwarmManagerAgent — not yet in dedicated orchestrator layer)

## Implemented Workers (21)

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

## Implemented SubAgents (7)

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

## Implemented Supervisors (5) — Phase 6 + Session 22
- `src/geosupply/supervisors/ingestion_supervisor.py`
- `src/geosupply/supervisors/quality_supervisor.py`
- `src/geosupply/supervisors/nlp_supervisor.py` — with InputSanitiserWorker pre-gate (Session 21)
- `src/geosupply/supervisors/intel_supervisor.py`
- `src/geosupply/supervisors/infra_supervisor.py` — Session 22; subscribes to watchdog.alert; cannot be paused; manages 9 infra singletons

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
- Schemas: `src/geosupply/schemas.py` (29 schemas — WatchdogAlert #28, FactCheckResult #29)
- Base classes and decorators: `src/geosupply/core/*.py`
  - `base_agent.py`: handle_event() with G3 HMAC verification (Session 21)
  - `event_bus.py`: verify_event() public interface (Session 21)
- Audit CLI baseline: `src/geosupply/cli/audit.py`

## Test Coverage
- Total tests: 747 (all passing — unit + integration; +73 in Session 22)
- Integration tests: `tests/integration/test_pipeline_integration.py`

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
Foundation + ingestion + NLP + intel workers (21/21) + subagents (10/13) + supervisors (5/14)
+ KnowledgeGraphAgent with SQLite + FactCheckAgent + SummarizationAuditAgent
+ InfraSupervisor + SwarmMaster DAG routing + GraphRAGSubAgent + BriefSynthSubAgent
+ SemanticDriftMonitor + integration tests + all G3 security fixes applied.

## Remaining Items (after Session 22)
1. Orchestrator (SwarmMaster class) — SwarmManagerAgent has decompose/execute_dag/route but no dedicated Layer 1 orchestrator class yet
2. 9 remaining supervisors (MLSupervisor, IndiaSupervisor, DashboardSupervisor, DevSupervisor, TestSupervisor, TechSupervisor, MarketingSupervisor, LoopholeHunterSupervisor, DisasterRecoverySupervisor)
3. 3 remaining subagents (OverridePatternSubAgent, MoAFallbackSubAgent, PenetrationTestSubAgent)
4. End-to-end integration test: full SUPPLY_BRIEF pipeline via execute_dag
