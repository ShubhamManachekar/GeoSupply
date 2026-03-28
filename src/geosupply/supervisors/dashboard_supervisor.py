"""
DashboardSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all dashboard agents (MetricPullAgent, AlertRenderAgent, KPIUpdateAgent).
Enforces budget gating and backpressure.

Domain: dashboard
Agents managed: MetricPullAgent, AlertRenderAgent, KPIUpdateAgent
Budget: ₹3/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_DASH_ROUTING: dict[str, str] = {
    "DASH_REFRESH":      "MetricPullAgent",
    "DASH_METRIC_PULL":  "MetricPullAgent",
    "DASH_ALERT_RENDER": "AlertRenderAgent",
    "DASH_KPI_UPDATE":   "KPIUpdateAgent",
    "DASH_ANY":          "MetricPullAgent",
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


class DashboardSupervisor(BaseSupervisor):
    """
    Controls the dashboard domain.

    Responsibilities:
      - Route dashboard tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹3/cycle).
      - Reject tasks when queue is full or budget exhausted.
    """

    name = "DashboardSupervisor"
    domain = "dashboard"
    budget_inr = 3.0
    agents = ["MetricPullAgent", "AlertRenderAgent", "KPIUpdateAgent"]

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
        Falls back to MetricPullAgent if unknown.
        """
        preferred = _DASH_ROUTING.get(task.task_type, "MetricPullAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using MetricPullAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["MetricPullAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
