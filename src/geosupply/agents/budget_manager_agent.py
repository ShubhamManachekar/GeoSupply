"""BudgetManagerAgent - INR budget gating and reservation tracking."""

from __future__ import annotations

from typing import Any

from geosupply.config import BUDGET_CAP_INR
from geosupply.core.base_agent import BaseAgent


class BudgetManagerAgent(BaseAgent):
    """Tracks reserved spend against a configurable INR cap."""

    name = "BudgetManagerAgent"
    domain = "control_plane"
    capabilities = {"BUDGET_GUARD", "BUDGET_RESERVE", "BUDGET_RELEASE"}
    max_concurrent = 1

    def __init__(self) -> None:
        super().__init__()
        self._cap_inr = float(BUDGET_CAP_INR)
        self._reserved_inr = 0.0

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        action = str(task.get("action", "status")).lower()
        try:
            amount = float(task.get("amount_inr", 0.0))
        except (TypeError, ValueError):
            return self._status("Invalid amount", approved=False)

        if action == "reserve":
            if amount <= 0:
                return self._status("Invalid reserve amount", approved=False)
            if self._reserved_inr + amount > self._cap_inr:
                return {
                    "result": {
                        "approved": False,
                        "reason": "BUDGET_EXCEEDED",
                        "reserved_inr": self._reserved_inr,
                        "cap_inr": self._cap_inr,
                    },
                    "meta": {"agent": self.name, "cost_inr": 0.0},
                }
            self._reserved_inr += amount
            return self._status("Reserved", approved=True)

        if action == "release":
            if amount <= 0:
                return self._status("Invalid release amount", approved=False)
            self._reserved_inr = max(0.0, self._reserved_inr - amount)
            return self._status("Released", approved=True)

        if action == "reset":
            self._reserved_inr = 0.0
            return self._status("Reset", approved=True)

        if action == "status":
            return self._status("Status")

        return self._status("Unknown action", approved=False)

    def _status(self, message: str, approved: bool = True) -> dict[str, Any]:
        return {
            "result": {
                "approved": approved,
                "message": message,
                "reserved_inr": round(self._reserved_inr, 2),
                "remaining_inr": round(self._cap_inr - self._reserved_inr, 2),
                "cap_inr": round(self._cap_inr, 2),
            },
            "meta": {"agent": self.name, "cost_inr": 0.01},
        }
