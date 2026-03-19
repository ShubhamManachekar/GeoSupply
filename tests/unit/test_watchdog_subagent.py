"""Tests for WatchdogSubAgent — Rule 10 compliance."""

import pytest
from unittest.mock import AsyncMock
from geosupply.subagents.watchdog_subagent import (
    WatchdogSubAgent,
    STUCK_BUSY_THRESHOLD_S,
    STUCK_ERROR_THRESHOLD_S,
)


class _FakeAgent:
    """Minimal agent stub for watchdog tests."""
    def __init__(self, name: str, state: str = "IDLE") -> None:
        self.name = name
        self.state = state


@pytest.fixture
async def watchdog():
    w = WatchdogSubAgent()
    await w.setup()
    yield w
    await w.teardown()


class TestRegistration:
    def test_register_agent(self):
        w = WatchdogSubAgent()
        agent = _FakeAgent("LoggingAgent")
        w.register_agent(agent)
        assert "LoggingAgent" in w._registered_agents

    def test_unregister_agent(self):
        w = WatchdogSubAgent()
        agent = _FakeAgent("LoggingAgent")
        w.register_agent(agent)
        w.unregister_agent("LoggingAgent")
        assert "LoggingAgent" not in w._registered_agents

    def test_register_captures_event_bus(self):
        w = WatchdogSubAgent()
        mock_bus = object()
        agent = _FakeAgent("X")
        w.register_agent(agent, event_bus=mock_bus)
        assert w._event_bus is mock_bus


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_all_idle_no_alerts(self, watchdog):
        for name in ("LoggingAgent", "SecurityAgent", "HealthCheckAgent"):
            watchdog.register_agent(_FakeAgent(name, "IDLE"))
        result = await watchdog.run({"trace_id": "wdg-001"})
        assert result["result"]["alert_count"] == 0
        assert result["result"]["agents_monitored"] == 3

    @pytest.mark.asyncio
    async def test_cost_always_zero(self, watchdog):
        result = await watchdog.run({"trace_id": "wdg-cost"})
        assert result["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_returns_agent_states(self, watchdog):
        watchdog.register_agent(_FakeAgent("A", "IDLE"))
        watchdog.register_agent(_FakeAgent("B", "BUSY"))
        result = await watchdog.run({"trace_id": "wdg-states"})
        states = result["result"]["agent_states"]
        assert states["A"] == "IDLE"
        assert states["B"] == "BUSY"


class TestAlertDetection:
    @pytest.mark.asyncio
    async def test_unreachable_agent_raises_alert(self, watchdog):
        class _Broken:
            name = "BrokenAgent"
            @property
            def state(self):
                raise RuntimeError("Cannot reach")

        watchdog.register_agent(_Broken())
        result = await watchdog.run({"trace_id": "wdg-unreach"})
        alerts = result["result"]["alerts"]
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "UNREACHABLE"

    @pytest.mark.asyncio
    async def test_stuck_busy_alert(self, watchdog):
        """Agent BUSY for longer than threshold → STUCK_BUSY alert."""
        agent = _FakeAgent("BusyAgent", "BUSY")
        watchdog.register_agent(agent)
        # Backdate state_entered_at
        from datetime import datetime, timezone, timedelta
        watchdog._state_entered_at["BusyAgent"] = (
            datetime.now(timezone.utc) - timedelta(seconds=STUCK_BUSY_THRESHOLD_S + 10)
        )
        watchdog._last_known_state["BusyAgent"] = "BUSY"

        result = await watchdog.run({"trace_id": "wdg-busy"})
        alerts = result["result"]["alerts"]
        assert any(a["alert_type"] == "STUCK_BUSY" for a in alerts)

    @pytest.mark.asyncio
    async def test_stuck_error_alert(self, watchdog):
        """Agent in ERROR for longer than threshold → STUCK_ERROR alert."""
        agent = _FakeAgent("ErrorAgent", "ERROR")
        watchdog.register_agent(agent)
        from datetime import datetime, timezone, timedelta
        watchdog._state_entered_at["ErrorAgent"] = (
            datetime.now(timezone.utc) - timedelta(seconds=STUCK_ERROR_THRESHOLD_S + 5)
        )
        watchdog._last_known_state["ErrorAgent"] = "ERROR"

        result = await watchdog.run({"trace_id": "wdg-error"})
        alerts = result["result"]["alerts"]
        assert any(a["alert_type"] == "STUCK_ERROR" for a in alerts)

    @pytest.mark.asyncio
    async def test_no_alert_for_short_busy(self, watchdog):
        """Agent BUSY briefly → no alert yet."""
        agent = _FakeAgent("NewBusy", "BUSY")
        watchdog.register_agent(agent)
        # state_entered_at defaults to NOW — well under threshold
        result = await watchdog.run({"trace_id": "wdg-ok-busy"})
        alerts = result["result"]["alerts"]
        assert not any(a["agent_name"] == "NewBusy" for a in alerts)

    @pytest.mark.asyncio
    async def test_recovered_alert(self, watchdog):
        """Agent transitions from alerted → IDLE → RECOVERED alert raised."""
        agent = _FakeAgent("RecoveringAgent", "IDLE")
        watchdog.register_agent(agent)
        # Simulate previously alerted
        watchdog._alerted_agents.add("RecoveringAgent")

        result = await watchdog.run({"trace_id": "wdg-recover"})
        alerts = result["result"]["alerts"]
        assert any(a["alert_type"] == "RECOVERED" for a in alerts)
        # Should no longer be in alerted set after recovery
        assert "RecoveringAgent" not in watchdog._alerted_agents

    @pytest.mark.asyncio
    async def test_no_double_alert(self, watchdog):
        """Agent already in alerted set → not re-alerted on same cycle."""
        agent = _FakeAgent("StuckBusyAgent", "BUSY")
        watchdog.register_agent(agent)
        from datetime import datetime, timezone, timedelta
        watchdog._state_entered_at["StuckBusyAgent"] = (
            datetime.now(timezone.utc) - timedelta(seconds=STUCK_BUSY_THRESHOLD_S + 60)
        )
        watchdog._last_known_state["StuckBusyAgent"] = "BUSY"
        watchdog._alerted_agents.add("StuckBusyAgent")  # pre-mark as alerted

        result = await watchdog.run({"trace_id": "wdg-no-dup"})
        stuck_alerts = [a for a in result["result"]["alerts"] if a["alert_type"] == "STUCK_BUSY"]
        assert len(stuck_alerts) == 0


class TestEventBusPublish:
    @pytest.mark.asyncio
    async def test_publishes_alert_when_bus_available(self, watchdog):
        """Published count matches alert count when event_bus is set."""
        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock(return_value=True)

        agent = _FakeAgent("BrokenAgent2")
        watchdog.register_agent(agent, event_bus=mock_bus)

        # Force unreachable
        class _Broken:
            name = "BrokenAgent2"
            @property
            def state(self):
                raise RuntimeError("dead")

        watchdog._registered_agents["BrokenAgent2"] = _Broken()
        result = await watchdog.run({"trace_id": "wdg-pub"})
        assert result["result"]["published"] == 1
        mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_publish_without_bus(self, watchdog):
        """Without event_bus, published == 0 even if alerts exist."""
        class _Broken:
            name = "BrokenAgent3"
            @property
            def state(self):
                raise RuntimeError("dead")

        watchdog._registered_agents["BrokenAgent3"] = _Broken()
        watchdog._state_entered_at["BrokenAgent3"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        watchdog._last_known_state["BrokenAgent3"] = "IDLE"

        result = await watchdog.run({"trace_id": "wdg-no-bus"})
        assert result["result"]["published"] == 0


class TestStats:
    def test_stats_property(self):
        w = WatchdogSubAgent()
        agent = _FakeAgent("A")
        w.register_agent(agent)
        s = w.stats
        assert s["agents_monitored"] == 1
        assert s["total_alerts_raised"] == 0
        assert isinstance(s["currently_alerted"], list)
