"""
NLPSupervisor - Phase 6 Supervisor Layer
FA v2 | Part V | Layer 2

Manages the NLP processing pipeline agents: sentiment, NER, claim extraction,
translation, and propaganda detection. Routes tasks to the appropriate NLP
agent and enforces budget gating.

Domain: nlp
Agents managed: SentimentAgent, NERAgent, ClaimAgent, TranslationAgent, PropagandaAgent
Budget: ₹8/cycle (NLP is Tier-1 STATIC — cheap)
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket
from geosupply.workers.input_sanitiser_worker import InputSanitiserWorker

logger = logging.getLogger(__name__)


# Task type → preferred NLP agent
_NLP_ROUTING: dict[str, str] = {
    "NLP_SENTIMENT":    "SentimentAgent",
    "NLP_NER":          "NERAgent",
    "NLP_CLAIM":        "ClaimAgent",
    "NLP_TRANSLATE":    "TranslationAgent",
    "NLP_PROPAGANDA":   "PropagandaAgent",
    "NLP_ENRICH":       "SentimentAgent",     # default enrichment → sentiment first
    "NLP_ANY":          "SentimentAgent",     # catch-all fallback
}

# NLP agent capability registry (for MoE routing hints)
_NLP_CAPABILITIES: dict[str, list[str]] = {
    "SentimentAgent":   ["SENTIMENT_ANALYSIS", "POLARITY_SCORE"],
    "NERAgent":         ["ENTITY_EXTRACTION", "GPE_DETECTION", "ORG_TAGGING"],
    "ClaimAgent":       ["CLAIM_CLASSIFY", "FACTUAL_DETECT", "EVIDENCE_FLAG"],
    "TranslationAgent": ["HINDI_EN", "URDU_EN", "TAMIL_EN", "BENGALI_EN"],
    "PropagandaAgent":  ["PROPAGANDA_DETECT", "NARRATIVE_CONTROL", "BOT_FLAG"],
}


class _StubAgent:
    """Minimal agent stub for supervisor tests without full agent instantiation."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = _NLP_CAPABILITIES.get(name, [])

    async def safe_execute(self, payload: dict) -> dict:
        return {
            "result": {"status": "stub_ok", "agent": self.name},
            "meta": {"cost_inr": 0.001, "agent": self.name},
        }


class NLPSupervisor(BaseSupervisor):
    """
    Controls the NLP processing domain.

    Responsibilities:
      - Route NLP tasks to Sentiment/NER/Claim/Translation/Propaganda agents.
      - Enforce ₹8/cycle budget cap (Tier-1 STATIC workers are cheap).
      - Reject tasks that exceed per-task budget.
      - Log routing decisions for audit trail.

    Budget: ₹8/cycle — NLP Tier-1 costs ~₹0.001/task (local llama3.2:3b).
    """

    name = "NLPSupervisor"
    domain = "nlp"
    budget_inr = 8.0
    agents = ["SentimentAgent", "NERAgent", "ClaimAgent", "TranslationAgent", "PropagandaAgent"]

    def __init__(self) -> None:
        self._agent_registry: dict[str, _StubAgent] = {
            agent_name: _StubAgent(agent_name) for agent_name in self.agents
        }
        self._sanitiser = InputSanitiserWorker()
        self.reset_budget()

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces stub at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def _select_agent(self, task: TaskPacket) -> _StubAgent:
        """Route to the appropriate NLP agent for the given task_type."""
        preferred = _NLP_ROUTING.get(task.task_type, "SentimentAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using SentimentAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["SentimentAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent

    async def dispatch(self, task: TaskPacket) -> dict:
        """
        Override BaseSupervisor.dispatch() to add InputSanitiserWorker pre-gate.

        Any 'text' field in task.payload is sanitised before routing.
        Suspicious inputs (injection detected) are rejected immediately.
        """
        text = task.payload.get("text")
        if text:
            trace_id = task.payload.get("trace_id", task.task_id)
            san_result = await self._sanitiser.process(
                {"text": text, "trace_id": trace_id}
            )
            # Sanitiser returned a WorkerError
            if "error_type" in san_result:
                return {
                    "status": "rejected",
                    "reason": f"sanitiser_error:{san_result['error_type']}",
                }
            result_data = san_result.get("result", {})
            if result_data.get("is_suspicious"):
                logger.warning(
                    "%s: injection detected in task %s — rejecting",
                    self.name, task.task_id,
                )
                return {"status": "rejected", "reason": "injection_detected"}
            # Replace raw text with sanitised text
            task = task.model_copy(
                update={"payload": {**task.payload, "text": result_data["sanitised_text"]}}
            )
        return await super().dispatch(task)

    def capable_agents(self, capability: str) -> list[str]:
        """Return list of agent names that support the given capability."""
        return [
            name for name, caps in _NLP_CAPABILITIES.items()
            if capability in caps
        ]
