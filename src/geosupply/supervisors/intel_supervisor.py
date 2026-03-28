"""
IntelSupervisor - Phase 6 Supervisor Layer
FA v2 | Part V | Layer 2

Manages the intelligence analysis pipeline: supply chain risk, sanctions screening,
source credibility, cyber threat analysis, claim verification, and author attribution.

Domain: intel
Agents managed: SupplierAgent, SanctionsAgent, SourceCredAgent, CyberAgent,
                VerifierAgent, AuthorAgent
Budget: ₹20/cycle (intel workers are Tier-1 to Tier-3 — more expensive)
"""

from __future__ import annotations

import logging

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket

logger = logging.getLogger(__name__)


# Task type → preferred intel agent
_INTEL_ROUTING: dict[str, str] = {
    "SUPPLY_CHAIN_RISK":  "SupplierAgent",
    "SANCTIONS_CHECK":    "SanctionsAgent",
    "SOURCE_CRED":        "SourceCredAgent",
    "CYBER_THREAT":       "CyberAgent",
    "VERIFY_CLAIM":       "VerifierAgent",
    "AUTHOR_CHECK":       "AuthorAgent",
    "INTEL_ANY":          "SourceCredAgent",   # default fallback
    "INTEL_ENRICH":       "CyberAgent",        # enrichment → cyber threat check
}

# Intel agent capability registry
_INTEL_CAPABILITIES: dict[str, list[str]] = {
    "SupplierAgent":   ["SUPPLY_CHAIN_RISK", "DEPENDENCY_MAP", "VENDOR_SCORE"],
    "SanctionsAgent":  ["SANCTIONS_CHECK", "ENTITY_SCREEN", "OFAC_LOOKUP"],
    "SourceCredAgent": ["SOURCE_CRED", "DOMAIN_TRUST", "STRIKE_REGISTRY"],
    "CyberAgent":      ["CYBER_THREAT", "MITRE_CLASSIFY", "APT_DETECT"],
    "VerifierAgent":   ["CLAIM_VERIFY", "EVIDENCE_CHECK", "CONTRADICTION_DETECT"],
    "AuthorAgent":     ["AUTHOR_CLASSIFY", "BOT_DETECT", "PROPAGANDA_FLAG"],
}

# Tier mapping for cost estimation per agent
_AGENT_TIER: dict[str, int] = {
    "SupplierAgent":   1,   # Tier-1 STATIC
    "SanctionsAgent":  1,   # Tier-1 STATIC
    "SourceCredAgent": 1,   # Tier-1 STATIC
    "CyberAgent":      1,   # Tier-1 STATIC
    "VerifierAgent":   3,   # Tier-3 (₹0.05/call)
    "AuthorAgent":     3,   # Tier-3 (₹0.05/call)
}

# Tier-3 tasks that warrant extra budget headroom
_TIER3_TASK_TYPES = {"VERIFY_CLAIM", "AUTHOR_CHECK"}


class _SupervisorAgentProxy:
    """Minimal agent proxy for supervisor tests for deferred runtime registration."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tier = _AGENT_TIER.get(name, 1)
        self.capabilities = _INTEL_CAPABILITIES.get(name, [])

    async def safe_execute(self, payload: dict) -> dict:
        cost = 0.05 if self.tier == 3 else 0.001
        return {
            "result": {"status": "stub_ok", "agent": self.name},
            "meta": {"cost_inr": cost, "agent": self.name, "tier": self.tier},
        }


class IntelSupervisor(BaseSupervisor):
    """
    Controls the intelligence analysis domain.

    Responsibilities:
      - Route intel tasks to the correct analysis agent by task_type.
      - Enforce ₹20/cycle budget cap across all intel agents.
      - Log routing + tier decisions for cost attribution.
      - Apply extra budget check for Tier-3 agents (VerifierAgent, AuthorAgent).

    Budget: ₹20/cycle — covers mix of Tier-1 (₹0.001) and Tier-3 (₹0.05) tasks.
    """

    name = "IntelSupervisor"
    domain = "intel"
    budget_inr = 20.0
    agents = [
        "SupplierAgent", "SanctionsAgent", "SourceCredAgent",
        "CyberAgent", "VerifierAgent", "AuthorAgent",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.agents = [
            "SupplierAgent", "SanctionsAgent", "SourceCredAgent",
            "CyberAgent", "VerifierAgent", "AuthorAgent",
        ]
        self._agent_registry: dict[str, _SupervisorAgentProxy] = {
            agent_name: _SupervisorAgentProxy(agent_name) for agent_name in self.agents
        }

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces proxy at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    async def dispatch(self, task: TaskPacket) -> dict:
        """
        Override dispatch to add Tier-3 budget pre-check.

        Tier-3 tasks (VERIFY_CLAIM, AUTHOR_CHECK) cost ₹0.05/call.
        If remaining budget < 0.05, reject Tier-3 tasks early.
        """
        if task.task_type in _TIER3_TASK_TYPES:
            if self._budget_remaining < 0.05:
                logger.warning(
                    "%s: rejecting Tier-3 task %s (type=%s) — budget exhausted (₹%.3f remaining)",
                    self.name, task.task_id, task.task_type, self._budget_remaining,
                )
                return {
                    "status": "rejected",
                    "reason": "budget_exhausted_tier3",
                    "task_id": task.task_id,
                    "budget_remaining_inr": self._budget_remaining,
                }

        return await super().dispatch(task)

    async def _select_agent(self, task: TaskPacket) -> _SupervisorAgentProxy:
        """Route to the appropriate intel agent for the given task_type."""
        preferred = _INTEL_ROUTING.get(task.task_type, "SourceCredAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using SourceCredAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["SourceCredAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s (tier=%s)",
            self.name, task.task_type, agent.name, agent.tier,
        )
        return agent

    def capable_agents(self, capability: str) -> list[str]:
        """Return list of agent names that support the given capability."""
        return [
            name for name, caps in _INTEL_CAPABILITIES.items()
            if capability in caps
        ]

    def tier3_agents(self) -> list[str]:
        """Return list of Tier-3 intel agents (higher cost, higher quality)."""
        return [name for name, tier in _AGENT_TIER.items() if tier == 3]
