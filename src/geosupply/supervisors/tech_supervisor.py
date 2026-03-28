"""
TechSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all technical operations agents (APIHealthAgent, DBCheckAgent,
CacheFlushAgent). Enforces budget gating and backpressure.

Custom dispatch gate: TECH_DB_CHECK with force_write=True is rejected
when budget_remaining < ₹1.00.

Domain: tech
Agents managed: APIHealthAgent, DBCheckAgent, CacheFlushAgent
Budget: ₹6/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_TECH_ROUTING: dict[str, str] = {
    "TECH_API_HEALTH":       "APIHealthAgent",
    "TECH_DB_CHECK":         "DBCheckAgent",
    "TECH_CACHE_FLUSH":      "CacheFlushAgent",
    "TECH_DEPENDENCY_AUDIT": "APIHealthAgent",
    "TECH_ANY":              "APIHealthAgent",
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


class TechSupervisor(BaseSupervisor):
    """
    Controls the technical operations domain.

    Responsibilities:
      - Route tech tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹6/cycle).
      - Reject tasks when queue is full or budget exhausted.
      - Custom gate: TECH_DB_CHECK + force_write=True rejected when budget < ₹1.
    """

    name = "TechSupervisor"
    domain = "tech"
    budget_inr = 6.0
    agents = ["APIHealthAgent", "DBCheckAgent", "CacheFlushAgent"]

    def __init__(self) -> None:
        super().__init__()
        self.agents = list(self.__class__.agents)
        self._agent_registry: dict[str, _SupervisorAgentProxy] = {
            agent_name: _SupervisorAgentProxy(agent_name) for agent_name in self.agents
        }

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces proxy at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def dispatch(self, task: TaskPacket) -> dict:
        """
        Override dispatch to add TECH_DB_CHECK force_write budget gate.

        If task_type == "TECH_DB_CHECK" and payload force_write is True
        and budget_remaining < ₹1.00, reject immediately.
        """
        if (
            task.task_type == "TECH_DB_CHECK"
            and task.payload.get("force_write") is True
            and self._budget_remaining < 1.0
        ):
            logger.warning(
                "%s: TECH_DB_CHECK with force_write=True rejected — "
                "budget_remaining=%.2f < 1.00",
                self.name, self._budget_remaining,
            )
            return {"status": "rejected", "reason": "db_write_budget_too_low"}
        return await super().dispatch(task)

    async def _select_agent(self, task: TaskPacket) -> _SupervisorAgentProxy:
        """
        Route to the preferred agent for the given task_type.
        Falls back to APIHealthAgent if unknown.
        """
        preferred = _TECH_ROUTING.get(task.task_type, "APIHealthAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using APIHealthAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["APIHealthAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
