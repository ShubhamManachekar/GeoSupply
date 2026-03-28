<!-- markdownlint-disable MD022 MD032 -->

# Actual State: Current Constraints

Date: March 28, 2026 (Updated: Session 28)

## Locked Rules to Preserve
- All costs tracked in INR.
- `HALLUCINATION_FLOOR = 0.70` never lowered.
- Typed schemas with version field.
- EventBus signing and verification behavior retained.
- Guarded state transitions for agents.

## Operational Reality Constraints (Updated: Session 28 — 2026-03-28)
- Control-plane manager agents (swarm/moe/budget/route) exist at Layer 3; all 14 supervisors now implemented.
- 13/13 SubAgents implemented (all complete). No subagents remain.
- 14/14 Supervisors implemented (all complete). No supervisors remain.
- SwarmMaster is now a dedicated class at `orchestrator/swarm_master.py` with 58-entry ROUTING_TABLE and SUPPLY_BRIEF_TEMPLATE (10 tasks). SwarmManagerAgent delegates to it for backward compat.
- InfraSupervisor and LoopholeHunterSupervisor and DisasterRecoverySupervisor: cannot be paused (`pause()` logs warning only).
- TechSupervisor: custom dispatch gate — TECH_DB_CHECK with force_write=True is rejected when `budget_remaining < ₹1.00`.
- Tier-1 STATIC mandatory workers are ALL implemented (SentimentWorker, NERWorker, ClaimWorker, SourceCredWorker, CyberThreatWorker, SupplierWorker, SanctionsWorker).

## New Constraints Added (Session 28)

### FastAPI REST API (`src/geosupply/api/`)
- Brief endpoint timeout: 120 seconds hard limit (returns 504 on timeout)
- Task store is in-process dict (not persistent) — replaced by Redis/Supabase in Phase 10+
- `get_swarm_master()` is a singleton via `lru_cache(maxsize=1)` — only one SwarmMaster per process
- Budget cap enforced at HTTP layer: `TaskSubmitRequest.budget_inr` field `le=500.0`
- Start server: `uvicorn geosupply.api.main:app --host 0.0.0.0 --port 8000 --reload`

### SwarmMaster (src/geosupply/orchestrator/swarm_master.py)
- NOT a BaseAgent subclass — no state machine, no capability advertising
- Single-writer: `_supervisor_registry` only writable via `register_supervisor()`
- ROUTING_TABLE is the single source of truth — imported by SwarmManagerAgent (backward compat)
- DAG deadlock detection: tasks with unresolvable dependencies are marked as `{"status":"skipped"}`

## Near-Term Risk Constraints
- OpenSky OAuth2 risk is documented against Phase 15 timing.
- Phase status statements in legacy trail must be interpreted with session-log and code evidence.
- Task store is in-memory only — data is lost on server restart until Phase 10 Redis integration.

Session 28b note: Documentation maintenance pass completed for active handoff docs; no architecture constraint changes introduced.
