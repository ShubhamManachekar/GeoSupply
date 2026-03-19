# Actual State: Current Constraints

Date: March 8, 2026

## Locked Rules to Preserve
- All costs tracked in INR.
- `HALLUCINATION_FLOOR = 0.70` never lowered.
- Typed schemas with version field.
- EventBus signing and verification behavior retained.
- Guarded state transitions for agents.

## Operational Reality Constraints (Updated: Session 21 — 2026-03-19)
- Control-plane manager agents (swarm/moe/budget/route) exist at Layer 3; supervisor execution tiers partially implemented (4/14).
- 7 SubAgents implemented (NLPPipeline, HallucinationCheck, AuditSample, SourceFeedback, RAGPipeline, WatchdogSubAgent, SourceClusterSubAgent). 6 planned subagents remain.
- 4 Supervisors implemented (Ingestion, Quality, NLP+pre-gate, Intel). 10 supervisors remain.
- Orchestrator (SwarmMaster.decompose() + DAG routing): NOT implemented. Round-robin lane splitting exists only.
- Tier-1 STATIC mandatory workers are ALL implemented (SentimentWorker, NERWorker, ClaimWorker, SourceCredWorker, CyberThreatWorker, SupplierWorker, SanctionsWorker).
- Most architecture promises in v9/v10/final for Phase 8+ (remaining supervisors, full MoE routing) remain design intent.
- InfraSupervisor not yet implemented — watchdog.alert events are published but have no subscriber/consumer.
- SwarmMaster.decompose(): Not implemented — blocking end-to-end pipeline execution.

## Near-Term Risk Constraints
- OpenSky OAuth2 risk is documented against Phase 15 timing.
- Phase status statements in legacy trail must be interpreted with session-log and code evidence.
