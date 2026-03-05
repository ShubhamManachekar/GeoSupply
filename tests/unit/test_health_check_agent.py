"""Unit tests for HealthCheckAgent — monitoring, health ratio, history."""

import pytest
from geosupply.agents.health_check_agent import HealthCheckAgent
from geosupply.config import AgentState
from geosupply.core.base_agent import BaseAgent


class DummyAgent(BaseAgent):
    name = "DummyAgent"
    domain = "test"
    capabilities = {"TEST"}
    async def execute(self, task): return {}


class ErrorAgent(BaseAgent):
    name = "ErrorAgent"
    domain = "test"
    capabilities = {"FAIL"}
    async def execute(self, task): raise RuntimeError("broken")


@pytest.fixture
def hc():
    return HealthCheckAgent()


class TestRegistration:
    def test_register_agent(self, hc):
        a = DummyAgent()
        hc.register_agent(a)
        assert "DummyAgent" in hc._registered_agents

    def test_unregister_agent(self, hc):
        a = DummyAgent()
        hc.register_agent(a)
        hc.unregister_agent("DummyAgent")
        assert "DummyAgent" not in hc._registered_agents


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_no_agents_returns_no_agents(self, hc):
        report = await hc.check()
        assert report["overall"] == "NO_AGENTS"

    @pytest.mark.asyncio
    async def test_all_healthy(self, hc):
        hc.register_agent(DummyAgent())
        report = await hc.check()
        assert report["overall"] == "HEALTHY"
        assert report["agents_healthy"] == 1
        assert report["health_ratio"] == 1.0

    @pytest.mark.asyncio
    async def test_degraded_status(self, hc):
        # 3 of 4 healthy = 75% → DEGRADED (≥70%)
        for i in range(3):
            a = DummyAgent()
            a.name = f"Good{i}"
            hc.register_agent(a)
        err = DummyAgent()
        err.name = "BadAgent"
        err._state = AgentState.ERROR
        hc.register_agent(err)

        report = await hc.check()
        assert report["overall"] == "DEGRADED"

    @pytest.mark.asyncio
    async def test_critical_status(self, hc):
        # 1 of 4 healthy = 25% → CRITICAL
        for i in range(3):
            a = DummyAgent()
            a.name = f"Bad{i}"
            a._state = AgentState.ERROR
            hc.register_agent(a)
        good = DummyAgent()
        good.name = "GoodOne"
        hc.register_agent(good)

        report = await hc.check()
        assert report["overall"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_check_records_history(self, hc):
        hc.register_agent(DummyAgent())
        await hc.check()
        await hc.check()
        assert len(hc._check_history) == 2

    @pytest.mark.asyncio
    async def test_history_capped_at_100(self, hc):
        hc.register_agent(DummyAgent())
        for _ in range(110):
            await hc.check()
        assert len(hc._check_history) == 100


class TestExecuteContract:
    @pytest.mark.asyncio
    async def test_execute_check(self, hc):
        hc.register_agent(DummyAgent())
        result = await hc.execute({"action": "check"})
        assert result["result"]["overall"] == "HEALTHY"
        assert result["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_execute_history(self, hc):
        hc.register_agent(DummyAgent())
        await hc.check()
        result = await hc.execute({"action": "history", "limit": 5})
        assert len(result["result"]["checks"]) == 1

    @pytest.mark.asyncio
    async def test_execute_unknown(self, hc):
        result = await hc.execute({"action": "bad"})
        assert "error" in result["result"]


class TestStats:
    @pytest.mark.asyncio
    async def test_stats(self, hc):
        hc.register_agent(DummyAgent())
        await hc.check()
        s = hc.stats
        assert s["monitored_agents"] == 1
        assert s["total_checks"] == 1
        assert s["last_check"] is not None
