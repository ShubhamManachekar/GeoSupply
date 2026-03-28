"""SwarmManagerAgent - control-plane task decomposition and parallel lane planning.

Backward-compatible wrapper: delegates decompose/execute_dag/route to SwarmMaster.
ROUTING_TABLE and SUPPLY_BRIEF_TEMPLATE are re-exported for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geosupply.core.base_agent import BaseAgent
from geosupply.schemas import TaskPacket

# Re-export from SwarmMaster for backward compatibility — noqa: F401
from geosupply.orchestrator.swarm_master import (  # noqa: F401
    ROUTING_TABLE,
    SUPPLY_BRIEF_TEMPLATE,
)


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

        Delegates to SwarmMaster.decompose() for the actual implementation.
        """
        from geosupply.orchestrator.swarm_master import SwarmMaster
        return SwarmMaster().decompose(compound_task)

    async def execute_dag(
        self,
        tasks: list[TaskPacket],
        supervisor_registry: dict,
    ) -> dict[str, dict]:
        """
        Execute TaskPackets in topological dependency order.

        Delegates to SwarmMaster.execute_dag() for the actual implementation.
        """
        from geosupply.orchestrator.swarm_master import SwarmMaster
        sm = SwarmMaster(supervisor_registry)
        return await sm.execute_dag(tasks)

    async def route(
        self,
        task: TaskPacket,
        supervisor_registry: dict,
    ) -> dict:
        """
        Route a single TaskPacket to its supervisor via ROUTING_TABLE.

        Delegates to SwarmMaster.route() for the actual implementation.
        """
        from geosupply.orchestrator.swarm_master import SwarmMaster
        sm = SwarmMaster(supervisor_registry)
        return await sm.route(task)
