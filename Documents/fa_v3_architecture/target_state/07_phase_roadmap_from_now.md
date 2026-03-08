# Target State: Phase Roadmap From Current State

Current baseline: Phase 2 + Phase 14 complete (plus extra implemented components outside table).

## Next Delivery Sequence
1. Phase 3: Core NLP/static extraction workers.
2. Phase 4: Intelligence workers and first domain agents.
3. Phase 5: Subagent pipeline layer activation.
4. Phase 6: Supervisor and orchestrator control-plane implementation.
5. Phase 7: Integrated MoE routing and budget governance.
6. Phase 8: Security hardening and operational controls.

## Dependency Rules
- Subagents cannot be production-routed before minimum worker coverage exists.
- Supervisors cannot be production-routed before agent/subagent contracts are stable.
- Orchestrator cannot be enabled without supervisor health and queue control tests.

## Phase Gate Template
- Implemented component checklist.
- Contract validation checklist.
- Audit strict pass.
- Coverage and regression pass.
- Risk register review.
