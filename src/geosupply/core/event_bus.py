"""
GeoSupply AI — EventBus
FA v2 | Part I, Part VIII | Cross-layer

Pub/sub event system for horizontal communication.
FA v2 G3: All events are signed with HMAC-SHA256 per-agent keys.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Awaitable

from geosupply.schemas import Event
from geosupply.config import EVENT_SIGNING_ALGO

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventSignatureError(Exception):
    """Raised when event signature verification fails."""
    pass


class EventBus:
    """
    Central pub/sub event bus.

    PATTERNS SUPPORTED (from Part I):
        FactCheckAgent ──quarantine_event──► SourceFeedbackSubAgent
        HealthCheckAgent ──alert_event──► SwarmMaster (DEGRADED_MODE)
        AuditorAgent ──drift_event──► RoutingAdvisor
        Worker.any ──cost_event──► BudgetManager
        LoopholeHunterAgent ──finding_event──► Admin (Telegram/Portal)

    FA v1 G3: Event Signing Protocol:
        1. Each agent gets a unique signing key from SecurityAgent
        2. signature = HMAC-SHA256(topic + source + payload_json + timestamp)
        3. EventBus verifies signature on every publish()
        4. Invalid signature → reject + log SECURITY_EVENT + alert admin
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._agent_keys: dict[str, str] = {}   # agent_name → signing key
        self._published: list[Event] = []        # audit trail
        self._signature_failures: int = 0

    # === Key Management (FA v1 G3) ===

    def register_agent_key(self, agent_name: str, signing_key: str) -> None:
        """Register a signing key for an agent. Called by SecurityAgent."""
        self._agent_keys[agent_name] = signing_key
        logger.info("EventBus: registered signing key for %s", agent_name)

    def revoke_agent_key(self, agent_name: str) -> None:
        """Revoke a signing key during rotation."""
        self._agent_keys.pop(agent_name, None)
        logger.info("EventBus: revoked signing key for %s", agent_name)

    # === Signing & Verification (FA v1 G3) ===

    @staticmethod
    def compute_signature(
        topic: str,
        source: str,
        payload: dict,
        timestamp: datetime,
        key: str,
    ) -> str:
        """Compute HMAC-SHA256 signature for an event."""
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        message = f"{topic}:{source}:{payload_json}:{timestamp.isoformat()}"
        return hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_signature(self, event: Event) -> bool:
        """Verify event signature against registered key."""
        key = self._agent_keys.get(event.source)
        if key is None:
            logger.error(
                "EventBus: no signing key for source '%s'", event.source
            )
            return False

        expected = self.compute_signature(
            event.topic, event.source, event.payload,
            event.timestamp, key,
        )
        return hmac.compare_digest(event.signature, expected)

    # === Pub/Sub ===

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Subscribe a handler to a topic."""
        self._subscribers[topic].append(handler)
        logger.debug("EventBus: subscribed handler to topic '%s'", topic)

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from a topic."""
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event, *, skip_verification: bool = False) -> bool:
        """
        Publish an event to all subscribers.

        Args:
            event: Signed Event object
            skip_verification: Only True for system-internal events (testing)

        Returns:
            True if published, False if rejected
        """
        # G3: Verify signature
        if not skip_verification:
            if not self._verify_signature(event):
                self._signature_failures += 1
                logger.error(
                    "SECURITY_EVENT: invalid signature from '%s' on topic '%s'. "
                    "Total failures: %d",
                    event.source, event.topic, self._signature_failures,
                )
                return False

        # Audit trail
        self._published.append(event)

        # Deliver to subscribers
        handlers = self._subscribers.get(event.topic, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                logger.error(
                    "EventBus: handler error for topic '%s': %s",
                    event.topic, exc,
                )

        return True

    # === Utilities ===

    def get_published(self, topic: str | None = None) -> list[Event]:
        """Get published events, optionally filtered by topic."""
        if topic:
            return [e for e in self._published if e.topic == topic]
        return list(self._published)

    @property
    def subscriber_count(self) -> dict[str, int]:
        return {topic: len(handlers) for topic, handlers in self._subscribers.items()}

    def __repr__(self) -> str:
        return (
            f"<EventBus topics={len(self._subscribers)} "
            f"published={len(self._published)} "
            f"sig_failures={self._signature_failures}>"
        )
