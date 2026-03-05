# Agent Template — BaseAgent with State Machine

## Template

```python
"""
[AgentName] — [one-line description]
Part of: GeoSupply AI FA v1
Layer: 3 (Agent)
Group: [A-G] — [Group name]
Phase: [build phase number]
"""

from datetime import datetime
from typing import Literal
from geosupply.core.base_agent import BaseAgent
from geosupply.core.decorators import tracer, cost_tracker, internal_breaker


class InvalidStateTransition(Exception):
    pass


class [AgentName](BaseAgent):
    """
    [Detailed description]

    DOMAIN: [domain area]
    CAPABILITIES: [list]
    MANAGES: [workers/subagents managed]
    """

    name = "[AgentName]"
    domain = "[domain]"
    capabilities = {"[CAP_1]", "[CAP_2]"}
    max_concurrent = 3
    _state: Literal["IDLE", "BUSY", "DONE", "ERROR", "RECOVERY"] = "IDLE"

    # FA v1 G2: State transition guards
    _VALID_TRANSITIONS = {
        "IDLE":     {"BUSY"},
        "BUSY":     {"DONE", "ERROR"},
        "DONE":     {"IDLE"},
        "ERROR":    {"RECOVERY"},
        "RECOVERY": {"IDLE"},
    }

    def _transition(self, new_state: str) -> None:
        if new_state not in self._VALID_TRANSITIONS.get(self._state, set()):
            raise InvalidStateTransition(
                f"{self.name}: {self._state} → {new_state} not allowed"
            )
        self._prev_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.utcnow()

    def advertise_capabilities(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "capabilities": list(self.capabilities),
            "cost_per_call_inr": 0.0,
            "avg_latency_ms": 0,
        }

    @tracer
    @cost_tracker
    @internal_breaker(timeout_s=30, max_failures=3)
    async def execute(self, task: dict) -> dict:
        """Main execution entry point."""
        self._transition("BUSY")
        try:
            result = await self._do_work(task)
            self._transition("DONE")
            self._transition("IDLE")
            return result
        except Exception as e:
            self._transition("ERROR")
            self._transition("RECOVERY")
            # Recovery logic here
            self._transition("IDLE")
            return {"error": str(e), "cost_inr": 0.0}

    async def _do_work(self, task: dict) -> dict:
        """Override this with actual agent logic."""
        raise NotImplementedError
```
