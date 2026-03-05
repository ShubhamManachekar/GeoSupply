"""Unit tests for BaseAgent — G2 state machine, safe_execute, capabilities."""

import pytest
from geosupply.config import AgentState
from geosupply.core.base_agent import BaseAgent, InvalidStateTransition


class TestAgent(BaseAgent):
    name = "TestAgent"
    domain = "test"
    capabilities = {"TEST_CAP"}

    async def execute(self, task: dict) -> dict:
        return {
            "result": {"done": True},
            "meta": {"agent": self.name, "cost_inr": 0.0},
        }


class FailAgent(BaseAgent):
    name = "FailAgent"
    domain = "test"
    capabilities = {"FAIL"}

    async def execute(self, task: dict) -> dict:
        raise RuntimeError("agent failure")


class TestStateMachine:
    def test_initial_state_is_idle(self):
        a = TestAgent()
        assert a.state == "IDLE"
        assert a.is_idle

    def test_valid_transition_idle_to_busy(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        assert a.state == "BUSY"

    def test_valid_full_cycle(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        a._transition(AgentState.DONE)
        a._transition(AgentState.IDLE)
        assert a.is_idle

    def test_valid_error_recovery_cycle(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        a._transition(AgentState.ERROR)
        a._transition(AgentState.RECOVERY)
        a._transition(AgentState.IDLE)
        assert a.is_idle

    def test_invalid_idle_to_done(self):
        a = TestAgent()
        with pytest.raises(InvalidStateTransition, match="IDLE.*DONE.*not allowed"):
            a._transition(AgentState.DONE)

    def test_invalid_idle_to_error(self):
        a = TestAgent()
        with pytest.raises(InvalidStateTransition):
            a._transition(AgentState.ERROR)

    def test_invalid_busy_to_idle(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        with pytest.raises(InvalidStateTransition):
            a._transition(AgentState.IDLE)

    def test_invalid_error_to_idle(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        a._transition(AgentState.ERROR)
        with pytest.raises(InvalidStateTransition):
            a._transition(AgentState.IDLE)  # Must go through RECOVERY

    def test_prev_state_tracked(self):
        a = TestAgent()
        a._transition(AgentState.BUSY)
        assert a._prev_state == AgentState.IDLE
        assert a._state_changed_at is not None


class TestSafeExecute:
    @pytest.mark.asyncio
    async def test_success_returns_to_idle(self):
        a = TestAgent()
        result = await a.safe_execute({"task": "test"})
        assert result["result"]["done"] is True
        assert a.is_idle

    @pytest.mark.asyncio
    async def test_failure_recovers_to_idle(self):
        a = FailAgent()
        result = await a.safe_execute({"task": "test"})
        assert result["meta"]["error"] is not None
        assert a.is_idle  # Recovery should bring back to IDLE


class TestAdvertise:
    def test_capabilities(self):
        a = TestAgent()
        caps = a.advertise_capabilities()
        assert caps["name"] == "TestAgent"
        assert caps["domain"] == "test"
        assert "TEST_CAP" in caps["capabilities"]
