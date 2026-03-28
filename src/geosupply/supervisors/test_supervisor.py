"""
TestSupervisor - Phase 6 Supervisor Layer
FA v3 | Layer 2

Manages all test-runner agents (UnitTestAgent, IntegrationTestAgent,
CoverageAgent). Enforces budget gating and backpressure.

Domain: testing
Agents managed: UnitTestAgent, IntegrationTestAgent, CoverageAgent
Budget: ₹4/cycle
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_TEST_ROUTING: dict[str, str] = {
    "TEST_UNIT_RUN":        "UnitTestAgent",
    "TEST_INTEGRATION_RUN": "IntegrationTestAgent",
    "TEST_COVERAGE_CHECK":  "CoverageAgent",
    "TEST_REGRESSION":      "UnitTestAgent",
    "TEST_ANY":             "UnitTestAgent",
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


class _TestSupervisorImpl(BaseSupervisor):
    """
    Controls the test-running domain.

    Responsibilities:
      - Route test tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹4/cycle).
      - Reject tasks when queue is full or budget exhausted.
    """

    name = "TestSupervisor"
    __test__ = False
    domain = "testing"
    budget_inr = 4.0
    agents = ["UnitTestAgent", "IntegrationTestAgent", "CoverageAgent"]

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
        Falls back to UnitTestAgent if unknown.
        """
        preferred = _TEST_ROUTING.get(task.task_type, "UnitTestAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using UnitTestAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["UnitTestAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent


# Public name used in ROUTING_TABLE and imports
TestSupervisor = _TestSupervisorImpl
