# Governance: Canonical Source Precedence

## Precedence Order
1. Code in `src/geosupply` (highest truth for implementation).
2. Session-level evidence in `Documents/DEVELOPMENT_TRAIL.md`.
3. FA v3 `actual_state/*`.
4. FA v3 `target_state/*`.
5. Legacy architecture docs (`v9_architecture`, `v10_architecture`, `final_architecture`).

## Conflict Resolution
If two sources disagree, the higher-precedence source wins and lower-precedence sources must be updated or marked stale.

## Enforcement Intent
No architecture claim is treated as implemented unless it can be traced to code and tests.
