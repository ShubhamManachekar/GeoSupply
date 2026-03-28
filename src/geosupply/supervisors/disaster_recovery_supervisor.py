"""
DisasterRecoverySupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all disaster recovery agents (BackupAgent, CostProjectionAgent,
RestoreAgent, FailoverAgent). Enforces budget gating and backpressure.

Cannot be paused — DR infrastructure must always remain active.

Domain: disaster_recovery
Agents managed: BackupAgent, CostProjectionAgent, RestoreAgent, FailoverAgent
Budget: ₹2/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_DR_ROUTING: dict[str, str] = {
    "BACKUP_RUN":       "BackupAgent",
    "COST_PROJECT":     "CostProjectionAgent",
    "DR_RESTORE":       "RestoreAgent",
    "DR_FAILOVER":      "FailoverAgent",
    "DR_HEALTH_CHECK":  "BackupAgent",
    "DR_ANY":           "BackupAgent",
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


class DisasterRecoverySupervisor(BaseSupervisor):
    """
    Controls the disaster recovery domain.

    Responsibilities:
      - Route DR tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹2/cycle).
      - Reject tasks when queue is full or budget exhausted.
      - Cannot be paused — DR must always remain active.
    """

    name = "DisasterRecoverySupervisor"
    domain = "disaster_recovery"
    budget_inr = 2.0
    agents = ["BackupAgent", "CostProjectionAgent", "RestoreAgent", "FailoverAgent"]

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
        """DisasterRecoverySupervisor cannot be paused — DR must stay active."""
        logger.warning(
            "%s: pause() called but DisasterRecoverySupervisor cannot be paused. "
            "Ignoring request.",
            self.name,
        )
        # Intentionally do NOT set self._is_paused = True

    async def _select_agent(self, task: TaskPacket) -> _SupervisorAgentProxy:
        """
        Route to the preferred agent for the given task_type.
        Falls back to BackupAgent if unknown.
        """
        preferred = _DR_ROUTING.get(task.task_type, "BackupAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using BackupAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["BackupAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
