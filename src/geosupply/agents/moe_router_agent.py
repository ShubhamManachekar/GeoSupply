"""MoERouterAgent - capability and cost-aware route selection."""

from __future__ import annotations

from typing import Any

from geosupply.core.base_agent import BaseAgent


class MoERouterAgent(BaseAgent):
    """Chooses the best expert route from candidate options."""

    name = "MoERouterAgent"
    domain = "control_plane"
    capabilities = {"MOE_ROUTE", "CAPABILITY_MATCH", "COST_AWARE_SELECTION"}
    max_concurrent = 3

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        candidates = task.get("candidates") or []
        required_capability = task.get("required_capability")

        if not isinstance(candidates, list) or not candidates:
            return {
                "result": {
                    "selected": None,
                    "reason": "No candidates provided",
                },
                "meta": {"agent": self.name, "cost_inr": 0.01},
            }

        valid_candidates = [c for c in candidates if isinstance(c, dict)]
        if not valid_candidates:
            return {
                "result": {
                    "selected": None,
                    "reason": "No valid candidate objects provided",
                },
                "meta": {"agent": self.name, "cost_inr": 0.01},
            }

        def _to_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def score(candidate: dict[str, Any]) -> tuple[float, float, float]:
            caps_raw = candidate.get("capabilities", [])
            caps = set(caps_raw) if isinstance(caps_raw, (list, tuple, set)) else set()
            cap_fit = 1.0 if not required_capability or required_capability in caps else 0.0
            confidence = _to_float(candidate.get("confidence", 0.0), default=0.0)
            cost = _to_float(candidate.get("cost_inr", 9999.0), default=9999.0)
            return (cap_fit, confidence, -cost)

        selected = max(valid_candidates, key=score)
        return {
            "result": {
                "selected": selected,
                "required_capability": required_capability,
            },
            "meta": {"agent": self.name, "cost_inr": 0.02},
        }
