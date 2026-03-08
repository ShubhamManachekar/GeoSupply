# Target State: FA v3 Layer Model

## Layer Stack
- Layer 0: Human and operator interfaces (CLI/Portal).
- Layer 1: Orchestrator (SwarmMaster) for decomposition, routing, and budget governance.
- Layer 2: Tier-based manager supervisors for domain scheduling and queue/budget gates.
- Layer 3: Domain agents coordinating workflows and stateful decision logic.
- Layer 4: Subagents composing pipelines across workers.
- Layer 5: Workers performing specialized execution tasks.
- Layer 6: Model and skill pool (Tier 0/1/2/3 model routing and capability registry).
- Cross-layer: Loophole/audit sentinel (read-only analysis, no execution side effects).

## Best-of-Worlds Composition
- Agentic: autonomous but bounded decision units per domain agent.
- Swarm: multi-supervisor parallelism with workload partitioning.
- MoE: capability and cost-aware selection of worker/agent paths.

## Manager-Agent Tier (Layer 3 Control Plane Slice)
- SwarmManagerAgent: task decomposition and parallel lane assignment.
- MoERouterAgent: capability and cost-aware expert selection.
- BudgetManagerAgent: INR guardrails, reserve/release, and cap state.
- RouteManagerAgent: primary/fallback planning with queue awareness.

## Implementation Guard
No layer is considered implemented in FA v3 until code classes exist and tests cover core contracts.
