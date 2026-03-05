"""
GeoSupply AI — InMemoryEventBus (FA v1 G10)
Non-side-effect event bus for testing. No signing required.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Awaitable

from geosupply.schemas import Event


class InMemoryEventBus:
    """
    In-memory event bus for unit/integration testing.
    No HMAC signing verification — uses skip_verification mode.
    """

    def __init__(self) -> None:
        self.published: list[Event] = []
        self.subscribers: dict[str, list[Callable[[Event], Awaitable[None]]]] = (
            defaultdict(list)
        )

    async def publish(self, event: Event, **kwargs) -> bool:
        """Publish without signature verification."""
        self.published.append(event)
        for handler in self.subscribers.get(event.topic, []):
            await handler(event)
        return True

    def subscribe(self, topic: str, handler: Callable) -> None:
        self.subscribers[topic].append(handler)

    def get_published(self, topic: str | None = None) -> list[Event]:
        if topic:
            return [e for e in self.published if e.topic == topic]
        return list(self.published)

    def clear(self) -> None:
        """Reset state between tests."""
        self.published.clear()
        self.subscribers.clear()
