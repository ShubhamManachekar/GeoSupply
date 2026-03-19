# Target State: Component Census (FA v3)

## Status Model
- Implemented: present in codebase and test-covered.
- Planned: architecture-defined but not yet implemented.

## Target Census
- Workers: 45 (Planned)
- SubAgents: 15 (Planned)
- Agents: 39 (Planned)
- Supervisors: 14 (Planned)
- Orchestrator: 1 (Planned)

## Current Baseline Comparison (Updated: Session 22 — 2026-03-19)
- Workers: 19 implemented (of 45 planned)
- Agents: 11 implemented (of 39 planned)
- SubAgents: 10 implemented (of 15 planned)
- Supervisors: 5 implemented (of 14 planned)
- Orchestrator: 0 implemented (DAG routing exists in SwarmManagerAgent, not dedicated class)

## Rule
Target census is never used as an implementation claim; only `actual_state/*` can assert implemented counts.
