"""Tests for InfraSupervisor."""

import pytest

from geosupply.supervisors.infra_supervisor import InfraSupervisor
from geosupply.schemas import TaskPacket, WatchdogAlert, Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_type: str, budget_inr: float = 1.0) -> TaskPacket:
    return TaskPacket(
        task_id=f"t-{task_type.lower()}",
        task_type=task_type,
        budget_inr=budget_inr,
        priority="P1",
    )


def _make_watchdog_event(
    agent_name: str,
    alert_type: str,
    trace_id: str = "trace-001",
    state_at_alert: str = "BUSY",
) -> Event:
    """Build a fake Event wrapping a WatchdogAlert payload (no signing needed)."""
    payload = {
        "agent_name": agent_name,
        "alert_type": alert_type,
        "state_at_alert": state_at_alert,
        "trace_id": trace_id,
        "stuck_duration_s": 120.0,
    }
    return Event(
        topic="watchdog.alert",
        source="WatchdogSubAgent",
        payload=payload,
        signature="",
    )


# ---------------------------------------------------------------------------
# Minimal fake EventBus — avoids key-management complexity in unit tests
# ---------------------------------------------------------------------------

class _FakeEventBus:
    """Lightweight stand-in for EventBus that records subscriptions and allows
    manual delivery of events without signature verification."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def subscribe(self, topic: str, handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    async def deliver(self, event: Event) -> None:
        """Directly invoke all handlers registered for event.topic."""
        for handler in self._handlers.get(event.topic, []):
            await handler(event)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def supervisor():
    sup = InfraSupervisor()
    sup.reset_budget()
    return sup


@pytest.fixture
def fake_bus():
    return _FakeEventBus()


@pytest.fixture
def supervisor_with_bus(fake_bus):
    sup = InfraSupervisor(event_bus=fake_bus)
    sup.reset_budget()
    return sup, fake_bus


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInfraSupervisorInit:
    def test_name_and_domain(self):
        sup = InfraSupervisor()
        assert sup.name == "InfraSupervisor"
        assert sup.domain == "infra"

    def test_budget_inr(self):
        sup = InfraSupervisor()
        assert sup.budget_inr == 2.0

    def test_agents_declared(self):
        sup = InfraSupervisor()
        for expected in (
            "LoggingAgent", "HealthCheckAgent", "SecurityAgent",
            "FactCheckAgent", "BudgetManagerAgent", "RouteManagerAgent",
            "MoERouterAgent", "SwarmManagerAgent", "KnowledgeGraphAgent",
        ):
            assert expected in sup.agents

    def test_agent_registry_populated(self):
        sup = InfraSupervisor()
        for agent_name in sup.agents:
            assert agent_name in sup._agent_registry


class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_infra_health(self, supervisor):
        """INFRA_HEALTH routes to HealthCheckAgent and returns completed."""
        task = _make_task("INFRA_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_kg_canary(self, supervisor):
        """KG_CANARY routes to KnowledgeGraphAgent stub."""
        task = _make_task("KG_CANARY")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        # Verify the right stub was called by inspecting the returned agent name
        agent_name = result["result"]["meta"]["agent"]
        assert agent_name == "KnowledgeGraphAgent"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_type_falls_back(self, supervisor):
        """Unknown task_type falls back to LoggingAgent gracefully."""
        task = _make_task("TOTALLY_UNKNOWN_TYPE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        agent_name = result["result"]["meta"]["agent"]
        assert agent_name == "LoggingAgent"

    @pytest.mark.asyncio
    async def test_dispatch_infra_log(self, supervisor):
        task = _make_task("INFRA_LOG")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert result["result"]["meta"]["agent"] == "LoggingAgent"

    @pytest.mark.asyncio
    async def test_dispatch_schema_migrate(self, supervisor):
        task = _make_task("SCHEMA_MIGRATE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert result["result"]["meta"]["agent"] == "LoggingAgent"


class TestCannotBePaused:
    def test_pause_does_not_set_is_paused(self, supervisor):
        """pause() MUST NOT set _is_paused=True for InfraSupervisor."""
        supervisor.pause()
        assert supervisor._is_paused is False

    @pytest.mark.asyncio
    async def test_dispatch_still_works_after_pause_called(self, supervisor):
        """Tasks continue to be accepted even if pause() is called."""
        supervisor.pause()
        task = _make_task("INFRA_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"


class TestBudgetGate:
    @pytest.mark.asyncio
    async def test_budget_gate_rejects_when_exhausted(self, supervisor):
        """budget_remaining=0 → rejected with reason=budget_exhausted."""
        supervisor._budget_remaining = 0.0
        task = _make_task("INFRA_HEALTH", budget_inr=0.5)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_budget_resets_to_full(self, supervisor):
        """reset_budget() restores the full budget_inr amount."""
        supervisor._budget_remaining = 0.0
        supervisor.reset_budget()
        assert supervisor._budget_remaining == supervisor.budget_inr
        # And tasks can be dispatched again
        task = _make_task("INFRA_HEALTH", budget_inr=0.5)
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"


class TestQueueFull:
    @pytest.mark.asyncio
    async def test_queue_full_rejects(self, supervisor):
        """Setting max_queue_depth=0 immediately triggers queue_full rejection."""
        supervisor.max_queue_depth = 0
        task = _make_task("INFRA_HEALTH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "queue_full"


class TestWatchdogIntegration:
    @pytest.mark.asyncio
    async def test_watchdog_alert_stuck_busy_triggers_recovery(
        self, supervisor_with_bus
    ):
        """STUCK_BUSY alert causes safe_execute(recover) on the matching stub."""
        supervisor, bus = supervisor_with_bus

        # Track calls to the HealthCheckAgent stub
        calls: list[dict] = []
        original_stub = supervisor._agent_registry["HealthCheckAgent"]

        async def capturing_safe_execute(payload: dict) -> dict:
            calls.append(payload)
            return {"result": {}, "meta": {"cost_inr": 0.0, "agent": "HealthCheckAgent"}}

        original_stub.safe_execute = capturing_safe_execute  # type: ignore[method-assign]

        event = _make_watchdog_event(
            agent_name="HealthCheckAgent",
            alert_type="STUCK_BUSY",
            trace_id="trace-xyz",
        )
        await bus.deliver(event)

        assert len(calls) == 1
        assert calls[0]["action"] == "recover"
        assert calls[0]["trace_id"] == "trace-xyz"

    @pytest.mark.asyncio
    async def test_watchdog_alert_stuck_error_triggers_recovery(
        self, supervisor_with_bus
    ):
        """STUCK_ERROR alert also triggers recovery."""
        supervisor, bus = supervisor_with_bus

        calls: list[dict] = []
        stub = supervisor._agent_registry["LoggingAgent"]

        async def capturing_safe_execute(payload: dict) -> dict:
            calls.append(payload)
            return {"result": {}, "meta": {"cost_inr": 0.0, "agent": "LoggingAgent"}}

        stub.safe_execute = capturing_safe_execute  # type: ignore[method-assign]

        event = _make_watchdog_event(
            agent_name="LoggingAgent",
            alert_type="STUCK_ERROR",
            trace_id="trace-err",
        )
        await bus.deliver(event)

        assert len(calls) == 1
        assert calls[0]["action"] == "recover"

    @pytest.mark.asyncio
    async def test_watchdog_alert_recovered_does_not_call_safe_execute(
        self, supervisor_with_bus
    ):
        """RECOVERED alert only logs; it must NOT call safe_execute."""
        supervisor, bus = supervisor_with_bus

        calls: list[dict] = []
        stub = supervisor._agent_registry["HealthCheckAgent"]

        async def capturing_safe_execute(payload: dict) -> dict:
            calls.append(payload)
            return {"result": {}, "meta": {"cost_inr": 0.0, "agent": "HealthCheckAgent"}}

        stub.safe_execute = capturing_safe_execute  # type: ignore[method-assign]

        event = _make_watchdog_event(
            agent_name="HealthCheckAgent",
            alert_type="RECOVERED",
        )
        await bus.deliver(event)

        assert calls == []  # no recovery triggered

    @pytest.mark.asyncio
    async def test_watchdog_no_event_bus_works_fine(self):
        """InfraSupervisor works correctly when no event_bus is supplied."""
        sup = InfraSupervisor()  # no event_bus kwarg
        sup.reset_budget()
        assert sup._event_bus is None
        task = _make_task("INFRA_HEALTH")
        result = await sup.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_watchdog_subscribes_to_correct_topic(self, fake_bus):
        """event_bus.subscribe is called with 'watchdog.alert' topic."""
        sup = InfraSupervisor(event_bus=fake_bus)
        assert "watchdog.alert" in fake_bus._handlers
        assert len(fake_bus._handlers["watchdog.alert"]) == 1

    @pytest.mark.asyncio
    async def test_watchdog_unknown_agent_does_not_raise(self, supervisor_with_bus):
        """Alert for an agent not in the registry is handled gracefully."""
        supervisor, bus = supervisor_with_bus
        event = _make_watchdog_event(
            agent_name="GhostAgent",
            alert_type="STUCK_BUSY",
            trace_id="trace-ghost",
        )
        # Should not raise
        await bus.deliver(event)
