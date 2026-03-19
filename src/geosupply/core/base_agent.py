"""
GeoSupply AI — BaseAgent
FA v2 | Part IV | Layer 3

Agents own a domain, manage worker/subagent pools, and advertise capabilities.
FA v1 G2: Explicit state machine with transition guards.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from geosupply.config import AgentState, VALID_STATE_TRANSITIONS

if TYPE_CHECKING:
    from geosupply.schemas import Event
    from geosupply.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class InvalidStateTransition(Exception):
    """Raised when an agent attempts an illegal state transition."""
    pass


class BaseAgent(ABC):
    """
    Abstract base for all 39 agents (FA v3 census target).

    STATE MACHINE:
        IDLE → BUSY → DONE → IDLE
                  ↓
              ERROR → RECOVERY → IDLE

    CAPABILITY ADVERTISING:
        Each agent declares what it can do for MoE routing.
    """

    name: str = "BaseAgent"
    domain: str = "default"
    max_concurrent: int = 3

    def __init__(self) -> None:
        # Instance-level mutable state (not class-level — prevents cross-instance leakage)
        self.capabilities: set[str] = set()
        # --- State Machine (FA v1 G2) ---
        self._state: AgentState = AgentState.IDLE
        self._prev_state: AgentState | None = None
        self._state_changed_at: datetime | None = None

    def _transition(self, new_state: AgentState) -> None:
        """
        FA v1 G2: Guarded state transition.

        Raises InvalidStateTransition if the transition is not in
        VALID_STATE_TRANSITIONS map.
        """
        allowed = VALID_STATE_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise InvalidStateTransition(
                f"{self.name}: {self._state.value} → {new_state.value} "
                f"is not allowed. Valid: {sorted(s.value for s in allowed)}"
            )
        self._prev_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.now(timezone.utc)
        logger.debug(
            "%s: state %s → %s", self.name,
            self._prev_state.value, self._state.value,
        )

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def is_idle(self) -> bool:
        return self._state == AgentState.IDLE

    def advertise_capabilities(self) -> dict:
        """Return capabilities for MoE routing."""
        return {
            "name": self.name,
            "domain": self.domain,
            "capabilities": sorted(self.capabilities),
            "cost_per_call_inr": 0.0,
            "avg_latency_ms": 0,
        }

    @abstractmethod
    async def execute(self, task: dict) -> dict:
        """Main execution entry point. Subclasses implement logic."""
        ...

    async def safe_execute(self, task: dict) -> dict:
        """
        Wrapper with state machine transitions and error recovery.
        Ensures agent always returns to IDLE regardless of outcome.
        """
        self._transition(AgentState.BUSY)
        try:
            result = await self.execute(task)
            self._transition(AgentState.DONE)
            self._transition(AgentState.IDLE)
            return result
        except Exception as exc:
            logger.error("%s: execution failed: %s", self.name, exc)
            self._transition(AgentState.ERROR)
            self._transition(AgentState.RECOVERY)
            # Recovery: attempt cleanup
            recovery_result = await self._recover(exc)
            self._transition(AgentState.IDLE)
            return recovery_result

    async def _recover(self, error: Exception) -> dict:
        """
        Override for custom recovery logic.
        Default: return error dict.
        """
        return {
            "result": None,
            "meta": {
                "agent": self.name,
                "cost_inr": 0.0,
                "error": str(error),
                "state": self._state.value,
            },
        }

    async def handle_event(
        self,
        event: "Event",
        event_bus: "EventBus | None" = None,
    ) -> None:
        """
        Process an inbound EventBus event.

        FA v1 G3: If event_bus is provided, verifies HMAC-SHA256 signature
        before dispatching. Events with invalid signatures are silently dropped
        and logged as SECURITY_EVENT.

        Subclasses override _on_event() for topic-specific handling.
        """
        if event_bus is not None and not event_bus.verify_event(event):
            logger.warning(
                "SECURITY_EVENT: %s rejected event from '%s' on topic '%s' "
                "— invalid HMAC signature",
                self.name, event.source, event.topic,
            )
            return
        await self._on_event(event)

    async def _on_event(self, event: "Event") -> None:
        """Override in subclasses to handle specific EventBus topics."""

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name} "
            f"domain={self.domain} state={self._state.value}>"
        )
