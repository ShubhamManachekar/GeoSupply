# Actual State: Current Constraints

Date: March 8, 2026

## Locked Rules to Preserve
- All costs tracked in INR.
- `HALLUCINATION_FLOOR = 0.70` never lowered.
- Typed schemas with version field.
- EventBus signing and verification behavior retained.
- Guarded state transitions for agents.

## Operational Reality Constraints
- Control-plane manager agents (swarm/moe/budget/route) exist at layer 3, but supervisor/orchestrator execution tiers remain unimplemented.
- No concrete subagent, supervisor, or orchestrator implementations yet.
- Tier-1 STATIC mandatory list exists in config, but corresponding workers are not implemented.
- Most architecture promises in v9/v10/final are currently design intent, not deployed behavior.

## Near-Term Risk Constraints
- OpenSky OAuth2 risk is documented against Phase 15 timing.
- Phase status statements in legacy trail must be interpreted with session-log and code evidence.
