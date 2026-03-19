# Target State: Phase Roadmap From Current State

Current baseline (Session 22): Phase 0-4 complete, Phase 6 (10/13 subagents), Phase 7 (partial KG), Phase 8 (5/14 supervisors + DAG routing), Phase 14 (audit) complete.

## Next Delivery Sequence
1. Phase 6 continuation: Remaining 9 supervisors (MLSupervisor, IndiaSupervisor, DashboardSupervisor, DevSupervisor, TestSupervisor, TechSupervisor, MarketingSupervisor, LoopholeHunterSupervisor, DisasterRecoverySupervisor).
2. Phase 6 continuation: Remaining 3 subagents (OverridePatternSubAgent, MoAFallbackSubAgent, PenetrationTestSubAgent).
3. Phase 8: Dedicated SwarmMaster orchestrator class (currently methods on SwarmManagerAgent).
4. Phase 5: ML workers and ConflictPredictor.
5. Phase 7 full: NetworkX DiGraph integration + ChromaDB embeddings in KnowledgeGraphAgent.
6. Phase 9: Admin CLI + Portal (12 pages).
7. Phase 8: Security hardening and operational controls.

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
