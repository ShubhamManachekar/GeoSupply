"""SwarmManagerAgent - control-plane task decomposition and parallel lane planning."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from geosupply.core.base_agent import BaseAgent


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
