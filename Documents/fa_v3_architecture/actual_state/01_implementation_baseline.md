# Actual State: Implementation Baseline

Date: March 19, 2026 (Session 21)

## Code-Verified Counts
- Workers implemented: 21
- Agents implemented: 11
- Subagents implemented: 7
- Supervisors implemented: 4
- Orchestrator implementations: 0

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

## Implemented Supervisors (4) — Phase 6
- `src/geosupply/supervisors/ingestion_supervisor.py`
- `src/geosupply/supervisors/quality_supervisor.py`
- `src/geosupply/supervisors/nlp_supervisor.py` — with InputSanitiserWorker pre-gate (Session 21)
- `src/geosupply/supervisors/intel_supervisor.py`

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
- Total tests: 674 (all passing — unit + integration)
- Integration tests: `tests/integration/test_pipeline_integration.py`

## Schemas
- Total schemas: 29
  - #1-25: original schemas
  - #26: VerificationResult (VerifierWorker)
  - #27: AuthorProfile (AuthorWorker)
  - #28: WatchdogAlert (WatchdogSubAgent) — Session 21
  - #29: FactCheckResult (FactCheckAgent) — Session 21
- All schemas registered in ALL_SCHEMAS and SCHEMA_VERSIONS (audit-verified)

## Status Label
Foundation + ingestion + NLP + intel workers (8/8) + subagents (7/13) + supervisors (4/14)
+ KnowledgeGraphAgent with SQLite + FactCheckAgent + SummarizationAuditAgent
+ integration tests + all G3 security fixes applied.

## Remaining High-Priority Items (→ target_state/09_component_design_backlog.md)
1. InfraSupervisor (P0) — watchdog.alert subscriber + restart handler
2. SwarmMaster.decompose() + DAG routing (P0) — no end-to-end pipeline yet
3. GraphRAGSubAgent (P1) — KG-enhanced vector retrieval
4. BriefSynthSubAgent (P1) — 3-proposer MoA + 4-level fallback
5. SemanticDriftMonitor (P2) — weekly KL divergence on source channels
