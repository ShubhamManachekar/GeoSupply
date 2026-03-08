# FA v3 Glossary

## Terms
- Implemented: Component exists in `src/geosupply` and is runnable/importable.
- Partially Implemented: Contract exists (base class/schema/config), but concrete domain implementation is missing.
- Planned: Architecture intent with no concrete implementation yet.
- Canonical: Highest-precedence source used when documents disagree.
- Control Plane: Routing, budgeting, orchestration, and policy decisions.
- Data Plane: Domain execution logic (workers/subagents/agents) and transformations.

## Phase Baseline Terms
- Phase-Complete: Planned gate met and code/tests exist.
- Extra-Phase Implementation: Implemented code that is outside current phase table rows.

## Locked Constraints
- All costs in INR.
- `HALLUCINATION_FLOOR = 0.70`.
- No lateral worker-to-worker or supervisor-to-supervisor communication.
- EventBus signing enabled for published events.
