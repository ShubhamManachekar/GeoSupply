# Target State: FA v3 Principles

## Design Goal
Combine the best of agentic execution, swarm orchestration, and MoE routing while preserving verifiable contracts and phased delivery realism.

## Locked Principles
1. Hierarchical execution: Worker < SubAgent < Agent < Supervisor < Orchestrator.
2. No lateral worker-to-worker or supervisor-to-supervisor communication.
3. Control-plane decisions are centralized and auditable.
4. Data-plane execution is typed, bounded, and failure-isolated.
5. All costs are tracked in INR and budget-gated.
6. Hallucination safety floor remains `0.70`.
7. Event publishing requires signature verification.
8. Schema evolution is explicit and version-aware.
9. Audit checks must be testable and not narrative-only.
10. Documentation must separate implemented vs planned state.
