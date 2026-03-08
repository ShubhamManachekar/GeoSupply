# Target State: MoE and Swarm Routing

## Routing Objective
Select execution paths by capability, confidence, cost, and latency while preserving hierarchy constraints.

## Tier-Based Manager Model
- Tier-M0: Ingestion and sanitation manager path.
- Tier-M1: Static-constrained extraction and lightweight scoring.
- Tier-M2: Mid-complexity correlation and network reasoning.
- Tier-M3: High-cost synthesis, verification, and briefing.

## Decision Inputs
- Task type and domain.
- Required confidence floor.
- Current budget headroom.
- Resource availability and queue depth.
- Prior failure signals and breaker states.

## Fallback Policy
1. Preferred route (best fit).
2. Lower-cost equivalent route.
3. Reduced-scope partial output route.
4. Manual escalation route.

## Non-Negotiables
- No lateral manager/supervisor calls.
- Every route decision emits traceable metadata.
- Budget and confidence guardrails are applied before dispatch.
