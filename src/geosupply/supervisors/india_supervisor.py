"""
IndiaSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all India-specific intelligence agents (IndiaPortAgent, IndiaMonsoonAgent,
IndiaPoliticalAgent, IndiaULIPAgent). Enforces budget gating and backpressure.

Domain: india
Agents managed: IndiaPortAgent, IndiaMonsoonAgent, IndiaPoliticalAgent, IndiaULIPAgent
Budget: ₹10/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_INDIA_ROUTING: dict[str, str] = {
    "INDIA_PORT_STATUS":    "IndiaPortAgent",
    "INDIA_MONSOON_IMPACT": "IndiaMonsoonAgent",
    "INDIA_POLITICAL_RISK": "IndiaPoliticalAgent",
    "INDIA_ULIP_QUERY":     "IndiaULIPAgent",
    "INDIA_REGIONAL_ALERT": "IndiaPoliticalAgent",
    "INDIA_ANY":            "IndiaPortAgent",
}


class _SupervisorAgentProxy:
    """Minimal agent proxy for supervisor tests for deferred runtime registration."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def safe_execute(self, payload: dict) -> dict:
        return {
            "result": {"status": "stub_ok", "agent": self.name},
            "meta": {"cost_inr": 0.0, "agent": self.name},
        }


class IndiaSupervisor(BaseSupervisor):
    """
    Controls the India intelligence domain.

    Responsibilities:
      - Route India-specific tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹10/cycle).
      - Reject tasks when queue is full or budget exhausted.
    """

    name = "IndiaSupervisor"
    domain = "india"
    budget_inr = 10.0
    agents = ["IndiaPortAgent", "IndiaMonsoonAgent", "IndiaPoliticalAgent", "IndiaULIPAgent"]

    def __init__(self) -> None:
        super().__init__()
        self.agents = list(self.__class__.agents)
        self._agent_registry: dict[str, _SupervisorAgentProxy] = {
            agent_name: _SupervisorAgentProxy(agent_name) for agent_name in self.agents
        }

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces proxy at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def _select_agent(self, task: TaskPacket) -> _SupervisorAgentProxy:
        """
        Route to the preferred agent for the given task_type.
        Falls back to IndiaPortAgent if unknown.
        """
        preferred = _INDIA_ROUTING.get(task.task_type, "IndiaPortAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using IndiaPortAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["IndiaPortAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
