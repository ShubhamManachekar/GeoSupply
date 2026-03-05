# Chapter 7: Orchestrator Layer — SwarmMaster + MoE Gateway

## Design Philosophy

> **The Orchestrator says WHAT, not HOW. It decomposes intent and routes to Supervisors.**

The SwarmMaster is the single entry point for ALL queries. It never executes work directly. It decomposes complex queries into sub-tasks, resolves dependencies, routes via MoE to the right Supervisor, and enforces global INR budgets.

---

## SwarmMaster Architecture

```python
class SwarmMaster:
    """
    Layer 1 Orchestrator — the brain of the swarm.

    COMPONENTS:
        MoE Gating Network     — routes tasks to appropriate supervisors
        Task Decomposer        — breaks complex queries into sub-tasks
        Dependency Resolver    — ensures task prerequisites are met
        Budget Manager (INR)   — global cost caps
        Session Coordinator    — max 6 parallel agent slots
        PipelineRectifier      — auto-corrects pipeline failures
        RoutingAdvisor         — reads advisory table for escalation
        ColdStartGuard         — DEGRADED_MODE if run_count < 3
        BackpressureController — NEW v9: manages system-wide load

    EXECUTION FLOW:
        1. Receive query/trigger
        2. ColdStartGuard check (run_count < 3?)
        3. Task Decomposer → list of TaskPackets
        4. Dependency Resolver → topological sort
        5. MoE Gating → route each TaskPacket to Supervisor
        6. Budget Manager → verify INR budget available
        7. Session Coordinator → allocate agent slots (max 6)
        8. Dispatch to Supervisors
        9. Collect results
        10. PipelineRectifier → handle any failures
        11. Return aggregated result
    """

    MAX_PARALLEL_AGENTS = 6  # PC GPU + RAM constraint

    def __init__(self):
        self.moe_gate = MoEGatingNetwork()
        self.decomposer = TaskDecomposer()
        self.resolver = DependencyResolver()
        self.budget = GlobalBudgetManager()
        self.session = SessionCoordinator(max_slots=6)
        self.rectifier = PipelineRectifierAgent()
        self.advisor = RoutingAdvisor()
        self.cold_start = ColdStartGuard()
        self.backpressure = BackpressureController()  # NEW v9

        # Register all 10 supervisors
        self._supervisors: dict[str, BaseSupervisor] = {}

    async def handle_query(self, query: str, context: dict = None) -> dict:
        """Main entry point for all queries."""

        # 1. Cold-start check
        if self.cold_start.is_cold():
            return await self._degraded_mode(query)

        # 2. Check routing advisories (escalate specific tasks)
        advisories = self.advisor.get_pending_advisories()

        # 3. Decompose into sub-tasks
        tasks = self.decomposer.decompose(query, context)

        # 4. Resolve dependencies (topological sort)
        ordered_tasks = self.resolver.resolve(tasks)

        # 5. Route and dispatch
        results = []
        for task_group in ordered_tasks:
            # Parallel tasks within a dependency level
            group_tasks = []
            for task in task_group:
                # Apply routing advisory if applicable
                task = self.advisor.apply(task, advisories)

                # MoE route to supervisor
                supervisor = self.moe_gate.route(task)

                # Budget check
                if not self.budget.can_spend(task.estimated_cost_inr):
                    return await self._degraded_mode(query)

                # Session slot check
                if not self.session.acquire_slot():
                    # Backpressure — queue for later
                    self.backpressure.defer(task)
                    continue

                group_tasks.append(supervisor.enqueue(task, task.priority))

            # Dispatch group
            for sup in self._active_supervisors():
                group_results = await sup.dispatch()
                results.extend(group_results)
                self.session.release_slots(len(group_results))

        return self._aggregate_results(results)
```

---

## MoE Gating Network v9.0

```python
class MoEGatingNetwork:
    """
    Routes TaskPackets to the correct Supervisor based on task type,
    model tier, and current system state.

    THREE-TIER MODEL ARCHITECTURE (LOCKED):
        Tier 1 — llama3.2:3b   (fast, schema-strict, STATIC decoder)
        Tier 2 — qwen2.5:14b   (multilingual, reasoning)
        Tier 3 — GPT-OSS:20b   (heavy reasoning, MoA synthesis)
    """

    ROUTING_TABLE = {
        # Task Type         → Supervisor        Tier  STATIC?
        "INGEST":            ("IngestSupervisor",  0, False),
        "EMBED":             ("NLPSupervisor",     0, False),
        "DETECT_LANG":       ("NLPSupervisor",     0, False),
        "XGBOOST_INFER":     ("MLSupervisor",      0, False),
        "CLASSIFY":          ("NLPSupervisor",      1, True),
        "NER":               ("NLPSupervisor",      1, True),
        "EXTRACT":           ("IntelSupervisor",    1, True),
        "SOURCE_SCORE":      ("IntelSupervisor",    1, True),
        "TRANSLATE_FAST":    ("NLPSupervisor",      1, True),
        "SOURCE_FEEDBACK":   ("QualitySupervisor",  1, True),
        "TRANSLATE_DEEP":    ("NLPSupervisor",      2, False),
        "MULTILINGUAL":      ("NLPSupervisor",      2, False),
        "AUDIT_SAMPLE":      ("InfraSupervisor",    2, False),
        "SEMANTIC_DRIFT":    ("InfraSupervisor",    2, False),
        "FACT_CHECK":        ("QualitySupervisor",  3, False),
        "AUTHOR_INTEL":      ("IntelSupervisor",    3, False),
        "RAG_PLAN":          ("IntelSupervisor",    3, False),
        "RAG_RETRIEVE":      ("IntelSupervisor",    0, False),
        "RAG_SYNTHESIZE":    ("IntelSupervisor",    3, False),
        "BRIEF_MOA":         ("IntelSupervisor",    3, False),
        "SCENARIO":          ("IntelSupervisor",    3, False),
        "CONVERGENCE":       ("IntelSupervisor",    3, False),
        "CONFLICT_PREDICT":  ("MLSupervisor",       0, False),
        "INDIA_API":         ("IndiaSupervisor",    0, False),
        "MONSOON_TRACK":     ("IndiaSupervisor",    0, False),
        "DASHBOARD_RENDER":  ("DashboardSupervisor",0, False),
        "EMERGENCY":         ("InfraSupervisor",    99, False),  # Claude API
    }

    FALLBACK_CHAINS = {
        # Primary              → Fallback 1           → Fallback 2
        "PC GPT-OSS:20b":     ["Groq llama-3.3-70b",  "Claude Sonnet"],
        "PC qwen2.5:14b":     ["Groq qwen-qwq-32b",   "GCP T4 qwen2.5:14b"],
        "Groq llama-3.1-8b":  ["CPU rule-based",       None],
    }

    def route(self, task: 'TaskPacket') -> 'BaseSupervisor':
        supervisor_name, tier, use_static = self.ROUTING_TABLE[task.task_type]
        task.tier = tier
        task.use_static = use_static
        return self._get_supervisor(supervisor_name)
```

---

## Task Decomposer

```python
class TaskDecomposer:
    """
    Breaks complex user queries into atomic TaskPackets.

    Examples:
        "What's the monsoon risk to Indian ports?" →
            1. TaskPacket(MONSOON_TRACK, priority=P1)   → IndiaSupervisor
            2. TaskPacket(RAG_PLAN, priority=P0)        → IntelSupervisor
            3. TaskPacket(STRESS_TEST, priority=P1)     → IntelSupervisor
            4. TaskPacket(BRIEF_MOA, priority=P0)       → IntelSupervisor

        "Ingest latest news and update dashboard" →
            1. TaskPacket(INGEST, priority=P0)           → IngestSupervisor
            2. TaskPacket(EMBED, priority=P1)            → NLPSupervisor
            3. TaskPacket(DASHBOARD_RENDER, priority=P2) → DashboardSupervisor
    """

    def decompose(self, query: str, context: dict = None) -> list['TaskPacket']:
        # Use Tier-3 model to decompose
        # Returns ordered list of TaskPackets with dependencies
        ...
```

---

## Session Coordinator — 6-Slot Budget

```
SLOT MANAGEMENT:
    Max 6 parallel agent slots (PC GPU + RAM constraint)
    Each Supervisor dispatch consumes 1+ slots
    Slots released when dispatch completes

    Slot allocation priority:
        P0 tasks: guaranteed 2 reserved slots
        P1 tasks: up to 3 slots
        P2-P3 tasks: remaining slots only

    If all 6 slots occupied + P0 task arrives:
        → Preempt lowest-priority running task
        → Deferred task re-queued with same priority
```

---

## DEGRADED_MODE & ColdStartGuard

```python
class ColdStartGuard:
    """
    Prevents empty-database failures on first runs.

    LOGIC:
        if pipeline_run_count < 3:
            DEGRADED_MODE activated
            Keep IngestSupervisor + IntelSupervisor alive
            (vector store too sparse for RAG-only output)
            Log IncidentRecord with cold_start=True
    """

    def is_cold(self) -> bool:
        run_count = self._get_run_count()  # From SQLite
        return run_count < 3

class DegradedMode:
    """
    Graceful degradation when budget/API/hardware unavailable.

    LEVELS:
        LEVEL 1 (Budget warning):
            Disable P3 tasks, continue P0-P2
        LEVEL 2 (API failures):
            IngestSupervisor + RAGWorker + DashboardWorker only
            IntelSupervisor stays alive if cold-start
        LEVEL 3 (Hardware offline):
            Groq-only mode (no PC models)
            All Tier-2/3 escalated to Groq fallback
        LEVEL 4 (Emergency):
            Claude API only for critical tasks
            INR 0.25/call — budget tracked strictly
    """
```
