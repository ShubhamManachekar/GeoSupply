# Target State: Delivery Backlog

## Priority Buckets
- P0: Control-plane minimum viable orchestration.
- P1: Tier-1 static worker coverage.
- P2: Subagent pipeline execution.
- P3: Full supervisor matrix and cross-domain routing.
- P4: Portal/ops hardening and long-horizon automation.

## Initial Work Packages
1. Implement first supervisor pair (ingestion + quality) with queue and budget gates.
2. Implement first subagent pair (RAG pipeline base + hallucination check).
3. Implement first static worker triad (sentiment, NER, claim) with contract tests.
4. Add orchestrator MVP for task decomposition and deterministic dispatch.
5. Add integration tests covering end-to-end signed event and error handling flows.

## Definition of Done (Backlog Item)
- Code merged.
- Unit tests and relevant integration tests passing.
- Audit strict unaffected or improved.
- `actual_state` docs updated.
