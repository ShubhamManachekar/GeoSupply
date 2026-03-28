"""
SwarmMaster — FA v3 Layer 1 Orchestrator
Dedicated control-plane class for compound task decomposition and DAG execution.
Extracted from SwarmManagerAgent to become the standalone Layer 1 entry point.

NOT a BaseAgent subclass — no state machine, no capability advertising.
Single-writer: _supervisor_registry only writable via register_supervisor().
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from geosupply.schemas import TaskPacket

# ROUTING_TABLE is the single source of truth — imported by SwarmManagerAgent too.
# Format: task_type → (supervisor_name, llm_tier, uses_static_decoder)
ROUTING_TABLE: dict[str, tuple[str, int, bool]] = {
    # Ingestion
    "INGEST_NEWS":              ("IngestionSupervisor",           0, False),
    "INGEST_INDIA_API":         ("IngestionSupervisor",           0, False),
    "INGEST_TELEGRAM":          ("IngestionSupervisor",           0, False),
    "INGEST_AIS":               ("IngestionSupervisor",           0, False),
    # NLP
    "NLP_SENTIMENT":            ("NLPSupervisor",                 1, True),
    "NLP_NER":                  ("NLPSupervisor",                 1, True),
    "NLP_CLAIM":                ("NLPSupervisor",                 1, True),
    "NLP_TRANSLATE":            ("NLPSupervisor",                 2, False),
    # Quality
    "CLAIM_VERIFY":             ("QualitySupervisor",             3, False),
    "HALLUCINATION_CHECK":      ("QualitySupervisor",             3, False),
    # Intel
    "SOURCE_SCORE":             ("IntelSupervisor",               1, True),
    "SUPPLIER_SCORE":           ("IntelSupervisor",               1, True),
    "SANCTIONS_CHECK":          ("IntelSupervisor",               1, True),
    "NARRATIVE_NETWORK":        ("IntelSupervisor",               2, False),
    "RAG_QUERY":                ("IntelSupervisor",               3, False),
    "BRIEF_GENERATE":           ("IntelSupervisor",               3, False),
    # Infra
    "INPUT_SANITISE":           ("InfraSupervisor",               0, False),
    "KG_CANARY":                ("InfraSupervisor",               0, False),
    "INFRA_HEALTH":             ("InfraSupervisor",               0, False),
    # DR
    "BACKUP_RUN":               ("DisasterRecoverySupervisor",    0, False),
    "COST_PROJECT":             ("DisasterRecoverySupervisor",    0, False),
    "DR_RESTORE":               ("DisasterRecoverySupervisor",    0, False),
    "DR_FAILOVER":              ("DisasterRecoverySupervisor",    0, False),
    "DR_HEALTH_CHECK":          ("DisasterRecoverySupervisor",    0, False),
    # ML
    "ML_STRESS_SCORE":          ("MLSupervisor",                  0, False),
    "ML_CONFLICT_PREDICT":      ("MLSupervisor",                  0, False),
    "ML_SUPPLIER_RANK":         ("MLSupervisor",                  0, False),
    "ML_SANCTION_CLASSIFY":     ("MLSupervisor",                  0, False),
    # India
    "INDIA_PORT_STATUS":        ("IndiaSupervisor",               0, False),
    "INDIA_MONSOON_IMPACT":     ("IndiaSupervisor",               0, False),
    "INDIA_POLITICAL_RISK":     ("IndiaSupervisor",               0, False),
    "INDIA_ULIP_QUERY":         ("IndiaSupervisor",               0, False),
    "INDIA_REGIONAL_ALERT":     ("IndiaSupervisor",               0, False),
    # Dashboard
    "DASH_REFRESH":             ("DashboardSupervisor",           0, False),
    "DASH_METRIC_PULL":         ("DashboardSupervisor",           0, False),
    "DASH_ALERT_RENDER":        ("DashboardSupervisor",           0, False),
    "DASH_KPI_UPDATE":          ("DashboardSupervisor",           0, False),
    # Dev
    "DEV_SCHEMA_VALIDATE":      ("DevSupervisor",                 0, False),
    "DEV_MIGRATION_RUN":        ("DevSupervisor",                 0, False),
    "DEV_TEST_RUN":             ("DevSupervisor",                 0, False),
    "DEV_LINT_CHECK":           ("DevSupervisor",                 0, False),
    # Test
    "TEST_UNIT_RUN":            ("TestSupervisor",                0, False),
    "TEST_INTEGRATION_RUN":     ("TestSupervisor",                0, False),
    "TEST_COVERAGE_CHECK":      ("TestSupervisor",                0, False),
    "TEST_REGRESSION":          ("TestSupervisor",                0, False),
    # Tech
    "TECH_API_HEALTH":          ("TechSupervisor",                0, False),
    "TECH_DB_CHECK":            ("TechSupervisor",                0, False),
    "TECH_CACHE_FLUSH":         ("TechSupervisor",                0, False),
    "TECH_DEPENDENCY_AUDIT":    ("TechSupervisor",                0, False),
    # Marketing
    "MARKETING_TWEET_GEN":      ("MarketingSupervisor",           2, False),
    "MARKETING_CONTENT_GEN":    ("MarketingSupervisor",           2, False),
    "MARKETING_ANALYTICS":      ("MarketingSupervisor",           0, False),
    "MARKETING_PREDICTION_POST":("MarketingSupervisor",           2, False),
    # Security
    "LOOPHOLE_SCAN":            ("LoopholeHunterSupervisor",      0, False),
    "LOOPHOLE_PEN_TEST":        ("LoopholeHunterSupervisor",      0, False),
    "LOOPHOLE_OVERRIDE_MONITOR":("LoopholeHunterSupervisor",      0, False),
    "LOOPHOLE_SCHEMA_AUDIT":    ("LoopholeHunterSupervisor",      0, False),
}

# 10-step SUPPLY_BRIEF pipeline template (dependency-ordered DAG)
SUPPLY_BRIEF_TEMPLATE: list[dict] = [
    {"task_type": "INGEST_NEWS",       "priority": "P1", "dependencies": []},
    {"task_type": "INGEST_INDIA_API",  "priority": "P1", "dependencies": []},
    {"task_type": "NLP_NER",           "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "NLP_SENTIMENT",     "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "NLP_CLAIM",         "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "SOURCE_SCORE",      "priority": "P1", "dependencies": ["NLP_NER", "NLP_SENTIMENT", "NLP_CLAIM"]},
    {"task_type": "CLAIM_VERIFY",      "priority": "P0", "dependencies": ["NLP_CLAIM"]},
    {"task_type": "NARRATIVE_NETWORK", "priority": "P1", "dependencies": ["NLP_NER", "SOURCE_SCORE"]},
    {"task_type": "RAG_QUERY",         "priority": "P0", "dependencies": ["NLP_NER", "NLP_CLAIM", "SOURCE_SCORE", "CLAIM_VERIFY"]},
    {"task_type": "BRIEF_GENERATE",    "priority": "P0", "dependencies": ["NARRATIVE_NETWORK", "RAG_QUERY"]},
]


class SwarmMaster:
    """
    FA v3 Layer 1 Orchestrator.

    Responsibilities:
      - Accept compound tasks and decompose them into atomic TaskPackets
      - Execute the resulting DAG respecting dependency order
      - Route each packet to the correct supervisor via ROUTING_TABLE
      - Provide run_supply_brief() as the high-level production entry point

    NOT a BaseAgent subclass — no state machine, no capability advertising.
    Single-writer: _supervisor_registry is only modified via register_supervisor().
    """

    def __init__(self, supervisor_registry: dict | None = None) -> None:
        # Single-writer: registry only modified via register_supervisor()
        self._supervisor_registry: dict = dict(supervisor_registry) if supervisor_registry else {}
        self._plan_count: int = 0

    def register_supervisor(self, name: str, supervisor: object) -> None:
        """Register a supervisor instance. Replaces any existing entry for that name."""
        self._supervisor_registry[name] = supervisor

    @property
    def registered_supervisors(self) -> list[str]:
        """Sorted list of registered supervisor names."""
        return sorted(self._supervisor_registry.keys())

    @property
    def plan_count(self) -> int:
        return self._plan_count

    def decompose(self, compound_task: dict) -> list[TaskPacket]:
        """
        Break a compound task into atomic TaskPackets with dependency edges.

        For "SUPPLY_BRIEF" compound_task_type: uses SUPPLY_BRIEF_TEMPLATE (10 packets).
        Each TaskPacket.task_id = f"{task_type}_{plan_id[:8]}".
        TaskPacket.dependencies contains task_ids (not task_types).
        Returns packets in SUPPLY_BRIEF_TEMPLATE order (already topological).
        Increments plan_count on each call.
        """
        plan_id = compound_task.get("plan_id") or str(uuid.uuid4())
        task_type = compound_task.get("compound_task_type", "SUPPLY_BRIEF")
        template = SUPPLY_BRIEF_TEMPLATE if task_type == "SUPPLY_BRIEF" else []

        # Build task_type → task_id mapping first (needed to resolve dependency ids)
        type_to_id: dict[str, str] = {
            step["task_type"]: f"{step['task_type']}_{plan_id[:8]}"
            for step in template
        }

        packets: list[TaskPacket] = []
        for step in template:
            tid = type_to_id[step["task_type"]]
            dep_ids = [type_to_id[d] for d in step["dependencies"] if d in type_to_id]
            packets.append(TaskPacket(
                task_id=tid,
                task_type=step["task_type"],
                priority=step["priority"],
                dependencies=dep_ids,
                payload=compound_task.get("payload", {}),
            ))

        self._plan_count += 1
        return packets

    async def execute_dag(
        self,
        tasks: list[TaskPacket],
        supervisor_registry: dict | None = None,
    ) -> dict[str, dict]:
        """
        Execute TaskPackets in topological dependency order.

        Uses self._supervisor_registry if no registry argument passed.

        Algorithm:
          1. Build pending map {task_id: TaskPacket}
          2. Build dep_map {task_id: set_of_dep_task_ids}
          3. Find tasks with all deps in completed → execute in parallel (asyncio.gather)
          4. Mark completed, repeat until pending is empty or deadlock detected
          5. Return {task_id: result_dict} for all executed tasks

        On exception in any single task: captures as {"status":"error","reason":str(exc)}
        On deadlock (no ready tasks, pending non-empty): marks remaining as "skipped".
        """
        registry = supervisor_registry if supervisor_registry is not None else self._supervisor_registry
        pending: dict[str, TaskPacket] = {t.task_id: t for t in tasks}
        completed: dict[str, dict] = {}
        dep_map: dict[str, set[str]] = {t.task_id: set(t.dependencies) for t in tasks}

        while pending:
            ready = [
                tid for tid, deps in dep_map.items()
                if tid in pending and deps.issubset(completed.keys())
            ]
            if not ready:
                # Deadlock or circular dependency — surface remaining tasks as skipped
                for tid in list(pending.keys()):
                    completed[tid] = {"status": "skipped", "reason": "dependency_unresolvable"}
                break

            results = await asyncio.gather(
                *[self.route(pending[tid], registry) for tid in ready],
                return_exceptions=True,
            )
            for tid, result in zip(ready, results):
                if isinstance(result, Exception):
                    completed[tid] = {"status": "error", "reason": str(result)}
                else:
                    completed[tid] = result
                del pending[tid]

        return completed

    async def route(
        self,
        task: TaskPacket,
        supervisor_registry: dict | None = None,
    ) -> dict:
        """
        Route a single TaskPacket to its supervisor via ROUTING_TABLE.

        Falls back to IngestionSupervisor if task_type not in ROUTING_TABLE.
        Returns {"status":"error","reason":...} if supervisor not registered.
        """
        registry = supervisor_registry if supervisor_registry is not None else self._supervisor_registry
        supervisor_name, _tier, _uses_static = ROUTING_TABLE.get(
            task.task_type, ("IngestionSupervisor", 0, False)
        )
        supervisor = registry.get(supervisor_name)
        if supervisor is None:
            return {
                "status": "error",
                "reason": f"supervisor {supervisor_name!r} not in registry",
            }
        return await supervisor.dispatch(task)

    async def run_supply_brief(
        self,
        payload: dict,
        plan_id: str | None = None,
    ) -> dict:
        """
        High-level production entry point: decompose SUPPLY_BRIEF + execute full DAG.

        Args:
            payload: raw intelligence payload (region, depth, etc.)
            plan_id: optional caller-supplied plan identifier (auto-generated if None)

        Returns:
            {
                "plan_id": str,
                "task_results": {task_id: result_dict},   # all 10 task results
                "total_cost_inr": float,                   # sum of all task costs
                "generated_at": iso8601 str,
            }
        """
        pid = plan_id or str(uuid.uuid4())
        tasks = self.decompose({"compound_task_type": "SUPPLY_BRIEF", "plan_id": pid, "payload": payload})
        task_results = await self.execute_dag(tasks)

        total_cost = sum(
            r.get("cost_inr", 0.0)
            for r in task_results.values()
            if isinstance(r, dict)
        )

        return {
            "plan_id": pid,
            "task_results": task_results,
            "total_cost_inr": round(total_cost, 6),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
