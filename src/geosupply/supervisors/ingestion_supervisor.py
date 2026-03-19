"""
IngestionSupervisor - Phase 6 Supervisor Layer
FA v2 | Part V | Layer 2

Manages all data ingestion agents (NewsWorker, IndiaAPIWorker,
TelegramWorker, AISWorker). Enforces budget gating, backpressure,
and source-selection priority.

Domain: ingestion
Agents managed: NewsAgent, IndiaAPIAgent, TelegramAgent, AISAgent (stubs)
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


# Priority routing table: task_type → preferred agent name
_INGESTION_ROUTING: dict[str, str] = {
    "INGEST_NEWS": "NewsAgent",
    "INGEST_INDIA_API": "IndiaAPIAgent",
    "INGEST_TELEGRAM": "TelegramAgent",
    "INGEST_AIS": "AISAgent",
    "INGEST_ANY": "NewsAgent",        # default fallback
}


class _StubAgent:
    """Minimal agent stub for supervisor tests without full agent instantiation."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def safe_execute(self, payload: dict) -> dict:
        return {
            "result": {"status": "stub_ok", "agent": self.name},
            "meta": {"cost_inr": 0.0, "agent": self.name},
        }


class IngestionSupervisor(BaseSupervisor):
    """
    Controls the ingestion domain.

    Responsibilities:
      - Route ingestion tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹15/cycle).
      - Reject tasks when queue is full or budget exhausted.
      - Log source priority decisions.
    """

    name = "IngestionSupervisor"
    domain = "ingestion"
    budget_inr = 15.0
    agents = ["NewsAgent", "IndiaAPIAgent", "TelegramAgent", "AISAgent"]

    def __init__(self) -> None:
        super().__init__()
        self.agents = ["NewsAgent", "IndiaAPIAgent", "TelegramAgent", "AISAgent"]
        # Initialise agent registry with stubs (replaced by real agents at runtime)
        self._agent_registry: dict[str, _StubAgent] = {
            agent_name: _StubAgent(agent_name) for agent_name in self.agents
        }

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces stub at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def _select_agent(self, task: TaskPacket) -> _StubAgent:
        """
        Route to the preferred agent for the given task_type.
        Falls back to NewsAgent if unknown.
        """
        preferred = _INGESTION_ROUTING.get(task.task_type, "NewsAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using NewsAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["NewsAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent

    def source_priority(self) -> list[str]:
        """Return agents ordered by ingestion priority."""
        return ["AISAgent", "TelegramAgent", "IndiaAPIAgent", "NewsAgent"]
