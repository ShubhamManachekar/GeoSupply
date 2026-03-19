"""
InfraSupervisor - Phase 6 Supervisor Layer
FA v2 | Part V | Layer 2

Manages all infrastructure agents (LoggingAgent, HealthCheckAgent,
SecurityAgent, FactCheckAgent, BudgetManagerAgent, RouteManagerAgent,
MoERouterAgent, SwarmManagerAgent, KnowledgeGraphAgent).

Enforces budget gating and backpressure. Cannot be paused.
Subscribes to watchdog.alert events for autonomous recovery.

Domain: infra
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from geosupply.core.base_supervisor import BaseSupervisor
from geosupply.schemas import TaskPacket, WatchdogAlert

if TYPE_CHECKING:
    from geosupply.core.event_bus import EventBus

logger = logging.getLogger(__name__)


# Priority routing table: task_type → preferred agent name
_INFRA_ROUTING: dict[str, str] = {
    "INFRA_HEALTH":    "HealthCheckAgent",
    "INFRA_LOG":       "LoggingAgent",
    "INFRA_WATCHDOG":  "HealthCheckAgent",
    "INFRA_RESTART":   "LoggingAgent",
    "KG_CANARY":       "KnowledgeGraphAgent",
    "SCHEMA_MIGRATE":  "LoggingAgent",
    "INPUT_SANITISE":  "LoggingAgent",
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


class InfraSupervisor(BaseSupervisor):
    """
    Controls the infrastructure domain.

    Responsibilities:
      - Route infra tasks to the correct agent by task_type.
      - Enforce budget_inr cap per cycle (default ₹2/cycle).
      - Reject tasks when queue is full or budget exhausted.
      - Cannot be paused — infrastructure must always remain active.
      - Subscribe to watchdog.alert events for autonomous agent recovery.
    """

    name = "InfraSupervisor"
    domain = "infra"
    budget_inr = 2.0
    agents = [
        "LoggingAgent",
        "HealthCheckAgent",
        "SecurityAgent",
        "FactCheckAgent",
        "BudgetManagerAgent",
        "RouteManagerAgent",
        "MoERouterAgent",
        "SwarmManagerAgent",
        "KnowledgeGraphAgent",
    ]

    def __init__(self, event_bus: "EventBus | None" = None) -> None:
        super().__init__()
        self.agents = [
            "LoggingAgent", "SecurityAgent", "HealthCheckAgent",
            "RouteManagerAgent", "MoERouterAgent", "SwarmManagerAgent",
            "KnowledgeGraphAgent",
        ]
        # Initialise agent registry with stubs (replaced by real agents at runtime)
        self._agent_registry: dict[str, _StubAgent] = {
            agent_name: _StubAgent(agent_name) for agent_name in self.agents
        }

        # Watchdog integration — subscribe to alerts if event_bus is provided
        self._event_bus = event_bus
        if event_bus is not None:
            event_bus.subscribe("watchdog.alert", self._on_watchdog_alert)
            logger.info(
                "%s: subscribed to watchdog.alert on event_bus", self.name
            )

    def register_agent(self, agent_name: str, agent: object) -> None:
        """Register a real BaseAgent instance (replaces stub at runtime)."""
        self._agent_registry[agent_name] = agent  # type: ignore[assignment]

    def pause(self) -> None:
        """InfraSupervisor cannot be paused — infrastructure must stay active."""
        logger.warning(
            "%s: pause() called but InfraSupervisor cannot be paused. "
            "Ignoring request.",
            self.name,
        )
        # Intentionally do NOT set self._is_paused = True

    async def _on_watchdog_alert(self, event: object) -> None:
        """
        Handle a watchdog.alert event from the EventBus.

        On STUCK_BUSY or STUCK_ERROR: trigger recovery on the affected agent stub.
        On RECOVERED: log an informational message.
        """
        from geosupply.schemas import Event as EventSchema  # local import avoids circularity

        # event may be an Event schema object whose payload contains the alert dict
        if hasattr(event, "payload"):
            payload = event.payload  # type: ignore[union-attr]
        else:
            payload = event  # type: ignore[assignment]

        try:
            alert = WatchdogAlert.model_validate(payload)
        except Exception as exc:
            logger.error(
                "%s: _on_watchdog_alert — failed to parse WatchdogAlert: %s",
                self.name, exc,
            )
            return

        if alert.alert_type in ("STUCK_BUSY", "STUCK_ERROR"):
            agent = self._agent_registry.get(alert.agent_name)
            if agent is not None:
                logger.warning(
                    "%s: watchdog alert %s for agent=%s trace_id=%s — "
                    "triggering recovery",
                    self.name, alert.alert_type, alert.agent_name, alert.trace_id,
                )
                await agent.safe_execute(
                    {"action": "recover", "trace_id": alert.trace_id}
                )
            else:
                logger.warning(
                    "%s: watchdog alert %s for unknown agent=%s — no stub found",
                    self.name, alert.alert_type, alert.agent_name,
                )
        elif alert.alert_type == "RECOVERED":
            logger.info(
                "%s: agent=%s has RECOVERED (trace_id=%s)",
                self.name, alert.agent_name, alert.trace_id,
            )

    async def _select_agent(self, task: TaskPacket) -> _StubAgent:
        """
        Route to the preferred agent for the given task_type.
        Falls back to LoggingAgent if unknown.
        """
        preferred = _INFRA_ROUTING.get(task.task_type, "LoggingAgent")
        agent = self._agent_registry.get(preferred)
        if agent is None:
            logger.warning(
                "%s: no agent found for task_type=%s, using LoggingAgent fallback",
                self.name, task.task_type,
            )
            agent = self._agent_registry["LoggingAgent"]

        logger.info(
            "%s: routing task_type=%s → agent=%s",
            self.name, task.task_type, agent.name,
        )
        return agent
