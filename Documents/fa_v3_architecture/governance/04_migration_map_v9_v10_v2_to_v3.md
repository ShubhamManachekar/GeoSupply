# Governance: Migration Map (v9, v10, v2 -> v3)

## Purpose
Map legacy architecture sets into FA v3 usage without deleting historical context.

## Mapping Rules
- `Documents/v9_architecture/*`: historical design context only.
- `Documents/v10_architecture/*`: expansion and hardening reference only.
- `Documents/final_architecture/*`: FA v2 design reference only.
- `Documents/fa_v3_architecture/actual_state/*`: implementation truth.
- `Documents/fa_v3_architecture/target_state/*`: planned architecture trajectory.

## Practical Guidance
When citing a legacy feature, always annotate whether it is:
- implemented now, or
- planned in FA v3 roadmap.

## Initial Migration Action
Treat all legacy docs as non-canonical for implementation counts and phase completion claims.
