# Target State: Control Plane vs Data Plane

## Control Plane
Responsibilities:
- Task decomposition.
- Capability matching and MoE routing.
- Budget gates and throttling.
- Priority and queue orchestration.
- Health, audit, and policy enforcement.

Components:
- Orchestrator, supervisors, policy/audit services.

## Data Plane
Responsibilities:
- Ingestion, NLP, intelligence extraction, scoring, and synthesis.
- Typed transformations and traceable outputs.
- Structured failure handling (`WorkerError` path).

Components:
- Agents, subagents, workers, model adapters.

## Boundary Rules
- Control plane does not execute domain payload logic.
- Data plane does not mutate orchestration policy state.
- Cross-plane communication is contract-bound and auditable.
