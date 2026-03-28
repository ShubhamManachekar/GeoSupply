"""
LoopholeHunterSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2 | Security

Manages all security scanning agents (LoopholeHunterAgent, PenTestAgent,
OverrideMonitorAgent). Enforces budget gating and backpressure.

Cannot be paused — security scanning must always remain active.

Domain: security
Agents managed: LoopholeHunterAgent, PenTestAgent, OverrideMonitorAgent
Budget: ₹5/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_LOOPHOLE_ROUTING: dict[str, str] = {
    "LOOPHOLE_SCAN":            "LoopholeHunterAgent",
    "LOOPHOLE_PEN_TEST":        "PenTestAgent",
    "LOOPHOLE_OVERRIDE_MONITOR":"OverrideMonitorAgent",
    "LOOPHOLE_SCHEMA_AUDIT":    "LoopholeHunterAgent",
    "LOOPHOLE_ANY":             "LoopholeHunterAgent",
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


class LoopholeHunterSupervisor(BaseSupervisor):
    """
    Controls the security scanning domain.

    Responsibilities:
      - Route security tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹5/cycle).
      - Reject tasks when queue is full or budget exhausted.
      - Cannot be paused — security must always remain active.
    """

    name = "LoopholeHunterSupervisor"
    domain = "security"
    budget_inr = 5.0
    agents = ["LoopholeHunterAgent", "PenTestAgent", "OverrideMonitorAgent"]

    def __init__(self) -> None:
        super().__init__()
        self.agents = list(self.__class__.agents)
        self._agent_registry: dict[str, _SupervisorAgentProxy] = {
            agent_name: _SupervisorAgentProxy(agent_name) for agent_name in self.agents
        }

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces proxy at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    def pause(self) -> None:
        """LoopholeHunterSupervisor cannot be paused — security must stay active."""
        logger.warning(
            "%s: pause() called but LoopholeHunterSupervisor cannot be paused. "
            "Ignoring request.",
            self.name,
        )
        # Intentionally do NOT set self._is_paused = True

    async def _select_agent(self, task: TaskPacket) -> _SupervisorAgentProxy:
        """
        Route to the preferred agent for the given task_type.
        Falls back to LoopholeHunterAgent if unknown.
        """
        preferred = _LOOPHOLE_ROUTING.get(task.task_type, "LoopholeHunterAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using LoopholeHunterAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["LoopholeHunterAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
