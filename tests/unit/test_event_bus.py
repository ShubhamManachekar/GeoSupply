"""Unit tests for EventBus — G3 signing, pub/sub, rejection."""

import pytest
from datetime import datetime
from geosupply.core.event_bus import EventBus, EventSignatureError
from geosupply.schemas import Event


@pytest.fixture
def bus():
    b = EventBus()
    b.register_agent_key("AgentA", "secret-key-aaa")
    b.register_agent_key("AgentB", "secret-key-bbb")
    return b


def _make_signed_event(bus: EventBus, source: str, key: str, topic: str = "test") -> Event:
    ts = datetime(2026, 3, 5, 12, 0, 0)
    payload = {"data": "hello"}
    sig = EventBus.compute_signature(topic, source, payload, ts, key)
    return Event(topic=topic, source=source, payload=payload, timestamp=ts, signature=sig)


class TestEventSigning:
    def test_valid_signature_verifies(self, bus):
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        assert bus._verify_signature(event)

    def test_wrong_key_fails(self, bus):
        event = _make_signed_event(bus, "AgentA", "wrong-key")
        assert not bus._verify_signature(event)

    def test_tampered_payload_fails(self, bus):
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        event.payload["data"] = "tampered"
        assert not bus._verify_signature(event)

    def test_unknown_agent_fails(self, bus):
        event = Event(topic="t", source="UnknownAgent", payload={}, signature="fake")
        assert not bus._verify_signature(event)

    def test_signature_is_deterministic(self):
        ts = datetime(2026, 1, 1)
        sig1 = EventBus.compute_signature("t", "s", {"a": 1}, ts, "k")
        sig2 = EventBus.compute_signature("t", "s", {"a": 1}, ts, "k")
        assert sig1 == sig2


class TestPubSub:
    @pytest.mark.asyncio
    async def test_publish_valid_event(self, bus):
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        result = await bus.publish(event)
        assert result is True
        assert len(bus.get_published()) == 1

    @pytest.mark.asyncio
    async def test_reject_invalid_signature(self, bus):
        event = _make_signed_event(bus, "AgentA", "wrong-key")
        result = await bus.publish(event)
        assert result is False
        assert len(bus.get_published()) == 0
        assert bus._signature_failures == 1

    @pytest.mark.asyncio
    async def test_subscriber_receives_event(self, bus):
        received = []

        async def handler(e: Event):
            received.append(e)

        bus.subscribe("test", handler)
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        await bus.publish(event)
        assert len(received) == 1
        assert received[0].source == "AgentA"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus):
        count = {"a": 0, "b": 0}

        async def handler_a(e):
            count["a"] += 1

        async def handler_b(e):
            count["b"] += 1

        bus.subscribe("test", handler_a)
        bus.subscribe("test", handler_b)
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        await bus.publish(event)
        assert count["a"] == 1
        assert count["b"] == 1

    @pytest.mark.asyncio
    async def test_skip_verification(self, bus):
        event = Event(topic="sys", source="System", payload={}, signature="none")
        result = await bus.publish(event, skip_verification=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_filter_by_topic(self, bus):
        e1 = _make_signed_event(bus, "AgentA", "secret-key-aaa", "topicA")
        e2 = _make_signed_event(bus, "AgentB", "secret-key-bbb", "topicB")
        await bus.publish(e1)
        await bus.publish(e2)
        assert len(bus.get_published("topicA")) == 1
        assert len(bus.get_published("topicB")) == 1
        assert len(bus.get_published()) == 2


class TestKeyManagement:
    def test_register_and_revoke(self):
        bus = EventBus()
        bus.register_agent_key("X", "key-x")
        assert "X" in bus._agent_keys
        bus.revoke_agent_key("X")
        assert "X" not in bus._agent_keys

    def test_subscriber_count(self):
        bus = EventBus()

        async def h(e):
            pass

        bus.subscribe("a", h)
        bus.subscribe("a", h)
        bus.subscribe("b", h)
        assert bus.subscriber_count == {"a": 2, "b": 1}


class TestUnsubscribe:
    def test_unsubscribe_removes_handler(self):
        """L112-114: unsubscribe actually removes the handler."""
        bus = EventBus()
        received = []

        async def handler(e):
            received.append(e)

        bus.subscribe("topic", handler)
        assert bus.subscriber_count["topic"] == 1
        bus.unsubscribe("topic", handler)
        assert bus.subscriber_count.get("topic", 0) == 0

    def test_unsubscribe_nonexistent_is_noop(self):
        """Unsubscribe handler not in list doesn't crash."""
        bus = EventBus()

        async def h1(e):
            pass

        async def h2(e):
            pass

        bus.subscribe("t", h1)
        bus.unsubscribe("t", h2)  # h2 was never subscribed
        assert bus.subscriber_count["t"] == 1


class TestHandlerException:
    @pytest.mark.asyncio
    async def test_handler_error_doesnt_break_publish(self, bus):
        """L146-147: If a handler throws, publish still returns True."""
        async def bad_handler(e):
            raise RuntimeError("handler exploded")

        good_received = []

        async def good_handler(e):
            good_received.append(e)

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        event = _make_signed_event(bus, "AgentA", "secret-key-aaa")
        result = await bus.publish(event)
        assert result is True  # Publish succeeds despite handler error
        assert len(good_received) == 1  # Good handler still ran


class TestRepr:
    def test_repr(self, bus):
        """L167: repr gives useful debug info."""
        r = repr(bus)
        assert "EventBus" in r
        assert "published=" in r
