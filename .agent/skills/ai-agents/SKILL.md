---
name: ai-agents
description: FA v3 guidelines for creating and modifying GeoSupply AI agents, subagents, and supervisors, focused on guarded state transitions, EventBus routing, and dynamic audit compliance.
---

# AI Agents Skill (FA v3)

## Architecture Context
The `ai-agents` skill covers Layers 2, 3, and 4 in the FA v3 model. Current implementation is concentrated in Layer 3 agents, including a manager-agent control plane slice.

### Locked FA v3 Rules for Agents
1. **DAG + Pydantic v2**: All agent inputs and outputs MUST be strongly typed using Pydantic v2 schemas defined in `schemas.py`.
2. **State Machine Transitions (G2)**: Every `BaseAgent` subclass MUST use `_transition()` for state changes based on `VALID_STATE_TRANSITIONS`.
    - `IDLE` → `BUSY` → `DONE` → `IDLE`
    - `BUSY` → `ERROR` → `RECOVERY` → `IDLE`
3. **No Lateral Communication**: Agents MUST NOT call other Agents directly. They only communicate downward to SubAgents/Workers or asynchronously via the `EventBus`.
4. **Single-Writer State**: Only Tier 0 authority.
5. **Cost Tracking**: Every agent execution (`execute()`, `run()`) must compute and return `cost_inr` inside a `meta` dictionary.

## Agent Types & Implementation
### BaseSupervisor (Layer 2)
- **Role**: Dispatches workloads, manages budgets natively, handles pause/resume cues.
- **Rule**: Does NOT process data. Only handles orchestration queue management.
- **Current State**: Concrete supervisor classes are still pending.

### BaseAgent (Layer 3)
- **Role**: Houses domain-specific logic and capabilities. Manage the state machine.
- **Rule**: Must define `name`, `domain`, and `capabilities` set.
- **Current State**: Includes manager-tier slice (`SwarmManagerAgent`, `MoERouterAgent`, `BudgetManagerAgent`, `RouteManagerAgent`) plus infrastructure/domain agents.

### BaseSubAgent (Layer 4)
- **Role**: Pipeline composition of multiple workers (parallel or sequential).
- **Hooks (G1)**: Must implement `setup()` and `teardown()` matching `BaseWorker`.
- **Rule**: SubAgents NEVER call other SubAgents (No nesting).
- **Current State**: Concrete subagent classes are pending.

## Hallucination & Scoring Guardrails
- **HALLUCINATION_FLOOR = 0.70**: No LLM operation should process or output data below this confidence threshold.
- **MoA Level 2 Scoring (G8)**: Use the weighted formula: `0.4 × factcheck + 0.3 × source_cred + 0.3 × evidence`. This MUST add up to 1.0. 

## Testing Contracts (ZERO MOCKS)
- Do NOT use `AsyncMock` to test the internal logic of an Agent.
- Use the **Real Component** approach as much as possible, leveraging `tests/fixtures/mock_worker.py` ONLY when simulating downstream workers that a Supervisor or Orchestrator depends on (G10).
- Provide real event data to test state transitions ensuring `InvalidStateTransition` exceptions trigger properly on invalid flows.
