"""
QualitySupervisor - Phase 6 Supervisor Layer
FA v2 | Part V | Layer 2

Governs the quality-assurance pipeline: NLP enrichment,
hallucination checks, and source credibility scoring.
Enforces that no output below HALLUCINATION_FLOOR reaches
downstream intelligence agents.

Domain: quality
Agents managed: NLPAgent, HallucinationAgent, SourceCredAgent (stubs)
"""

from __future__ import annotations

import logging

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


_QUALITY_ROUTING: dict[str, str] = {
    "NLP_ENRICH": "NLPAgent",
    "HALLUCINATION_CHECK": "HallucinationAgent",
    "SOURCE_CRED": "SourceCredAgent",
    "QUALITY_ANY": "NLPAgent",
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


class QualitySupervisor(BaseSupervisor):
    """
    Controls the quality-assurance domain.

    Responsibilities:
      - Route QA tasks to NLPAgent, HallucinationAgent, SourceCredAgent.
      - Enforce HALLUCINATION_FLOOR (0.70) as a dispatch precondition.
      - Reject tasks marked below floor (confidence < HALLUCINATION_FLOOR).
      - Budget ₹10/cycle (QA is CPU-heavy but not LLM-intensive).
    """

    name = "QualitySupervisor"
    domain = "quality"
    budget_inr = 10.0
    agents = ["NLPAgent", "HallucinationAgent", "SourceCredAgent"]

    def __init__(self) -> None:
        self._agent_registry: dict[str, _StubAgent] = {
            agent_name: _StubAgent(agent_name) for agent_name in self.agents
        }
        self.reset_budget()

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces stub at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def dispatch(self, task: TaskPacket) -> dict:
        """
        Override dispatch to enforce HALLUCINATION_FLOOR pre-check.

        If payload contains 'confidence' < HALLUCINATION_FLOOR, reject immediately.
        """
        confidence = task.payload.get("confidence")
        if confidence is not None and float(confidence) < HALLUCINATION_FLOOR:
            logger.warning(
                "%s: rejecting task %s — confidence %.3f below floor %.2f",
                self.name, task.task_id, confidence, HALLUCINATION_FLOOR,
            )
            return {
                "status": "rejected",
                "reason": "below_hallucination_floor",
                "confidence": confidence,
                "floor": HALLUCINATION_FLOOR,
            }

        return await super().dispatch(task)

    async def _select_agent(self, task: TaskPacket) -> _StubAgent:
        """Route to the correct QA agent for the given task_type."""
        preferred = _QUALITY_ROUTING.get(task.task_type, "NLPAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent for task_type=%s, using NLPAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["NLPAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent

    @property
    def hallucination_floor(self) -> float:
        """Expose the locked floor for introspection."""
        return HALLUCINATION_FLOOR
