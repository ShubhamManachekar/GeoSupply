"""
MarketingSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all marketing automation agents (TweetGenAgent, PredictionPostAgent,
AnalyticsAgent, ContentGenAgent). Enforces budget gating and backpressure.

Domain: marketing
Agents managed: TweetGenAgent, PredictionPostAgent, AnalyticsAgent, ContentGenAgent
Budget: ₹8/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_MARKETING_ROUTING: dict[str, str] = {
    "MARKETING_TWEET_GEN":       "TweetGenAgent",
    "MARKETING_PREDICTION_POST": "PredictionPostAgent",
    "MARKETING_ANALYTICS":       "AnalyticsAgent",
    "MARKETING_CONTENT_GEN":     "ContentGenAgent",
    "MARKETING_ANY":             "ContentGenAgent",
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


class MarketingSupervisor(BaseSupervisor):
    """
    Controls the marketing automation domain.

    Responsibilities:
      - Route marketing tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹8/cycle).
      - Reject tasks when queue is full or budget exhausted.
    """

    name = "MarketingSupervisor"
    domain = "marketing"
    budget_inr = 8.0
    agents = ["TweetGenAgent", "PredictionPostAgent", "AnalyticsAgent", "ContentGenAgent"]

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
        Falls back to ContentGenAgent if unknown.
        """
        preferred = _MARKETING_ROUTING.get(task.task_type, "ContentGenAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using ContentGenAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["ContentGenAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
