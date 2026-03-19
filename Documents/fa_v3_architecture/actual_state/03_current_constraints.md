# Actual State: Current Constraints

Date: March 19, 2026 (Updated: Session 22)

## Locked Rules to Preserve
- All costs tracked in INR.
- `HALLUCINATION_FLOOR = 0.70` never lowered.
- Typed schemas with version field.
- EventBus signing and verification behavior retained.
- Guarded state transitions for agents.

## Operational Reality Constraints (Updated: Session 22 — 2026-03-19)
- Control-plane manager agents (swarm/moe/budget/route) exist at Layer 3; supervisor execution tiers partially implemented (5/14).
- 10 SubAgents implemented (NLPPipeline, HallucinationCheck, AuditSample, SourceFeedback, RAGPipeline, WatchdogSubAgent, SourceClusterSubAgent, GraphRAGSubAgent, BriefSynthSubAgent, SemanticDriftMonitor). 3 planned subagents remain.
- 5 Supervisors implemented (Ingestion, Quality, NLP+pre-gate, Intel, Infra). 9 supervisors remain.
- SwarmManagerAgent has decompose() + execute_dag() + route() with ROUTING_TABLE (21 entries) and SUPPLY_BRIEF template. Dedicated orchestrator class not yet created.
- InfraSupervisor implemented (Session 22) — subscribes to watchdog.alert events; autonomous agent recovery; cannot be paused.
- Tier-1 STATIC mandatory workers are ALL implemented (SentimentWorker, NERWorker, ClaimWorker, SourceCredWorker, CyberThreatWorker, SupplierWorker, SanctionsWorker).
- Most architecture promises in v9/v10/final for Phase 8+ (remaining supervisors, full MoE routing) remain design intent.

## Near-Term Risk Constraints
- OpenSky OAuth2 risk is documented against Phase 15 timing.
- Phase status statements in legacy trail must be interpreted with session-log and code evidence.
