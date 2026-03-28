"""
MLSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all ML/scoring agents (StressScoreAgent, ConflictPredictAgent,
SupplierRankAgent, SanctionClassifyAgent). Enforces budget gating and backpressure.

Domain: ml
Agents managed: StressScoreAgent, ConflictPredictAgent, SupplierRankAgent, SanctionClassifyAgent
Budget: ₹12/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_ML_ROUTING: dict[str, str] = {
    "ML_STRESS_SCORE":      "StressScoreAgent",
    "ML_CONFLICT_PREDICT":  "ConflictPredictAgent",
    "ML_SUPPLIER_RANK":     "SupplierRankAgent",
    "ML_SANCTION_CLASSIFY": "SanctionClassifyAgent",
    "ML_ANY":               "StressScoreAgent",
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


class MLSupervisor(BaseSupervisor):
    """
    Controls the ML/scoring domain.

    Responsibilities:
      - Route ML tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹12/cycle).
      - Reject tasks when queue is full or budget exhausted.
    """

    name = "MLSupervisor"
    domain = "ml"
    budget_inr = 12.0
    agents = ["StressScoreAgent", "ConflictPredictAgent", "SupplierRankAgent", "SanctionClassifyAgent"]

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
        Falls back to StressScoreAgent if unknown.
        """
        preferred = _ML_ROUTING.get(task.task_type, "StressScoreAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using StressScoreAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["StressScoreAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
