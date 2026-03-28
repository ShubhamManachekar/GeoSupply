---
name: moe-orchestration
description: Mixture of Experts (MoE) routing, manager-agent control-plane behavior, INR budget caps, and dynamic capability-based route selection.
---

# MoE Orchestration Skill (FA v3)

## Context
FA v3 separates implementation truth from target state:
- Current code has a Layer 3 manager-agent control-plane slice (`SwarmManagerAgent`, `MoERouterAgent`, `BudgetManagerAgent`, `RouteManagerAgent`).
- Layer 1 orchestrator and Layer 2 supervisor execution tiers remain target-state design, not implemented runtime.

## Dynamic Capability Routing
- **No Hardcoded Tables**: Routing logic MUST NOT maintain hardcoded task-to-agent maps.
- Query `advertise_capabilities()` from discovered `BaseAgent` subclasses and route by capability fit, confidence, and cost.
- For control-plane manager logic, malformed payloads must be tolerated safely (reject or default), never crash route selection.

## The Locked ₹500/month Budget Cap
- **Strict Enforcement**: Costs are logged as `cost_inr` and tracked in INR only.
- Reserve/release workflows must reject invalid or unknown actions deterministically.
- At 80%+ of monthly cap, expensive routing paths must be throttled according to governance rules.

## Tier 0 Authority (Single-Writer)
- Tier 0 remains the single-writer authority in target state.
- `KnowledgeUpdateRequest` writes must remain gated by confidence and `HALLUCINATION_FLOOR = 0.70`.

## Implementation Guard
- No MoE/orchestration layer is considered complete until classes exist and tests pass through `python -m geosupply.cli.audit --level strict`.
