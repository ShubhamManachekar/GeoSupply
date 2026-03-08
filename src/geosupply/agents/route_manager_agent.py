"""RouteManagerAgent - fallback route planning for execution resilience."""

from __future__ import annotations

from typing import Any

from geosupply.core.base_agent import BaseAgent


class RouteManagerAgent(BaseAgent):
    """Builds deterministic fallback routes from route options."""

    name = "RouteManagerAgent"
    domain = "control_plane"
    capabilities = {"ROUTE_PLAN", "FALLBACK_PLAN", "QUEUE_AWARE_ROUTING"}
    max_concurrent = 3

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        routes = task.get("routes") or []
        if not isinstance(routes, list) or not routes:
            return {
                "result": {
                    "primary": None,
                    "fallbacks": [],
                    "reason": "No routes provided",
                },
                "meta": {"agent": self.name, "cost_inr": 0.01},
            }

        valid_routes = [r for r in routes if isinstance(r, dict)]
        if not valid_routes:
            return {
                "result": {
                    "primary": None,
                    "fallbacks": [],
                    "reason": "No valid route objects provided",
                },
                "meta": {"agent": self.name, "cost_inr": 0.01},
            }

        def _to_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def rank(route: dict[str, Any]) -> tuple[float, float, float]:
            confidence = _to_float(route.get("confidence", 0.0), default=0.0)
            queue_depth = _to_float(route.get("queue_depth", 9999.0), default=9999.0)
            cost = _to_float(route.get("cost_inr", 9999.0), default=9999.0)
            return (confidence, -queue_depth, -cost)

        ordered = sorted(valid_routes, key=rank, reverse=True)
        primary = ordered[0]
        fallbacks = ordered[1:4]

        return {
            "result": {
                "primary": primary,
                "fallbacks": fallbacks,
            },
            "meta": {"agent": self.name, "cost_inr": 0.02},
        }
