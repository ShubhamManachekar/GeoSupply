"""SwarmManagerAgent - control-plane task decomposition and parallel lane planning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geosupply.core.base_agent import BaseAgent
from geosupply.schemas import TaskPacket


ROUTING_TABLE: dict[str, tuple[str, int, bool]] = {
    # (supervisor_name, tier, uses_static)
    "INGEST_NEWS":         ("IngestionSupervisor",           0, False),
    "INGEST_INDIA_API":    ("IngestionSupervisor",           0, False),
    "INGEST_TELEGRAM":     ("IngestionSupervisor",           0, False),
    "INGEST_AIS":          ("IngestionSupervisor",           0, False),
    "NLP_SENTIMENT":       ("NLPSupervisor",                 1, True),
    "NLP_NER":             ("NLPSupervisor",                 1, True),
    "NLP_CLAIM":           ("NLPSupervisor",                 1, True),
    "NLP_TRANSLATE":       ("NLPSupervisor",                 2, False),
    "CLAIM_VERIFY":        ("QualitySupervisor",             3, False),
    "HALLUCINATION_CHECK": ("QualitySupervisor",             3, False),
    "SOURCE_SCORE":        ("IntelSupervisor",               1, True),
    "SUPPLIER_SCORE":      ("IntelSupervisor",               1, True),
    "SANCTIONS_CHECK":     ("IntelSupervisor",               1, True),
    "NARRATIVE_NETWORK":   ("IntelSupervisor",               2, False),
    "RAG_QUERY":           ("IntelSupervisor",               3, False),
    "BRIEF_GENERATE":      ("IntelSupervisor",               3, False),
    "INPUT_SANITISE":      ("InfraSupervisor",               0, False),
    "KG_CANARY":           ("InfraSupervisor",               0, False),
    "INFRA_HEALTH":        ("InfraSupervisor",               0, False),
    "BACKUP_RUN":          ("DisasterRecoverySupervisor",    0, False),
    "COST_PROJECT":        ("DisasterRecoverySupervisor",    0, False),
}

# Standard decomposition for SUPPLY_BRIEF compound task (T1..T10)
SUPPLY_BRIEF_TEMPLATE: list[dict] = [
    {"task_type": "INGEST_NEWS",      "priority": "P1", "dependencies": []},
    {"task_type": "INGEST_INDIA_API", "priority": "P1", "dependencies": []},
    {"task_type": "NLP_NER",          "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "NLP_SENTIMENT",    "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "NLP_CLAIM",        "priority": "P1", "dependencies": ["INGEST_NEWS", "INGEST_INDIA_API"]},
    {"task_type": "SOURCE_SCORE",     "priority": "P1", "dependencies": ["NLP_NER", "NLP_SENTIMENT", "NLP_CLAIM"]},
    {"task_type": "CLAIM_VERIFY",     "priority": "P0", "dependencies": ["NLP_CLAIM"]},
    {"task_type": "NARRATIVE_NETWORK","priority": "P1", "dependencies": ["NLP_NER", "SOURCE_SCORE"]},
    {"task_type": "RAG_QUERY",        "priority": "P0", "dependencies": ["NLP_NER", "NLP_CLAIM", "SOURCE_SCORE", "CLAIM_VERIFY"]},
    {"task_type": "BRIEF_GENERATE",   "priority": "P0", "dependencies": ["NARRATIVE_NETWORK", "RAG_QUERY"]},
]


class SwarmManagerAgent(BaseAgent):
    """Plans execution lanes for independent work items."""

    name = "SwarmManagerAgent"
    domain = "control_plane"
    capabilities = {"SWARM_COORDINATE", "TASK_DECOMPOSE", "PARALLEL_PLAN"}
    max_concurrent = 2

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        items = task.get("items") or []
        if not isinstance(items, list) or not items:
            return {
                "result": {
                    "route": "single_lane",
                    "lanes": [[task]],
                    "reason": "No explicit item list provided",
                },
                "meta": {"agent": self.name, "cost_inr": 0.03},
            }

        try:
            lane_count = int(task.get("lane_count", 2))
        except (TypeError, ValueError):
            lane_count = 2
        lane_count = max(1, min(lane_count, 8))
        lanes: list[list[Any]] = [[] for _ in range(lane_count)]

        # Round-robin allocation keeps deterministic behavior for auditability.
        for idx, item in enumerate(items):
            lanes[idx % lane_count].append(item)

        return {
            "result": {
                "route": "swarm_parallel",
                "lane_count": lane_count,
                "lanes": lanes,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "meta": {"agent": self.name, "cost_inr": 0.05},
        }

    def decompose(self, compound_task: dict) -> list[TaskPacket]:
        """
        Break a compound task into atomic TaskPackets with dependency edges.

        Recognises "SUPPLY_BRIEF" compound_task_type and uses SUPPLY_BRIEF_TEMPLATE.
        Each TaskPacket gets a unique task_id = f"{task_type}_{plan_id[:8]}".
        TaskPacket.dependencies is a list of task_ids (not task_types).
        Returns list ordered by SUPPLY_BRIEF_TEMPLATE (topological order already).
        """
        import uuid
        plan_id = compound_task.get("plan_id") or str(uuid.uuid4())
        task_type = compound_task.get("compound_task_type", "SUPPLY_BRIEF")
        template = SUPPLY_BRIEF_TEMPLATE if task_type == "SUPPLY_BRIEF" else []

        # Build task_type → task_id mapping first
        type_to_id: dict[str, str] = {}
        for step in template:
            tid = f"{step['task_type']}_{plan_id[:8]}"
            type_to_id[step["task_type"]] = tid

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
        return packets

    async def execute_dag(
        self,
        tasks: list[TaskPacket],
        supervisor_registry: dict,
    ) -> dict[str, dict]:
        """
        Execute TaskPackets in topological dependency order.

        Algorithm:
          1. Build adjacency: {task_id: set_of_dep_task_ids}
          2. Find tasks with no pending deps → execute in parallel
          3. Mark completed, unblock dependents, repeat
          4. Return {task_id: result} for all tasks
        """
        import asyncio
        pending = {t.task_id: t for t in tasks}
        completed: dict[str, dict] = {}
        dep_map = {t.task_id: set(t.dependencies) for t in tasks}

        while pending:
            # Tasks whose dependencies are all completed
            ready = [
                tid for tid, deps in dep_map.items()
                if tid in pending and deps.issubset(completed.keys())
            ]
            if not ready:
                # Circular or unresolvable — break to avoid infinite loop
                break

            results = await asyncio.gather(
                *[self.route(pending[tid], supervisor_registry) for tid in ready],
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
        supervisor_registry: dict,
    ) -> dict:
        """
        Route a single TaskPacket to its supervisor via ROUTING_TABLE.
        Falls back to IngestionSupervisor if task_type not found.
        """
        supervisor_name, _tier, _uses_static = ROUTING_TABLE.get(
            task.task_type, ("IngestionSupervisor", 0, False)
        )
        supervisor = supervisor_registry.get(supervisor_name)
        if supervisor is None:
            return {"status": "error", "reason": f"supervisor {supervisor_name!r} not in registry"}
        return await supervisor.dispatch(task)
