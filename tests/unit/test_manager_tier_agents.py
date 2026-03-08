"""Unit tests for manager-tier control-plane agents."""

import pytest

from geosupply.agents.budget_manager_agent import BudgetManagerAgent
from geosupply.agents.moe_router_agent import MoERouterAgent
from geosupply.agents.route_manager_agent import RouteManagerAgent
from geosupply.agents.swarm_manager_agent import SwarmManagerAgent


class TestSwarmManagerAgent:
    @pytest.mark.asyncio
    async def test_builds_parallel_lanes(self):
        agent = SwarmManagerAgent()
        res = await agent.execute({"items": [1, 2, 3, 4], "lane_count": 2})
        assert res["result"]["route"] == "swarm_parallel"
        assert res["result"]["lane_count"] == 2
        assert len(res["result"]["lanes"]) == 2

    @pytest.mark.asyncio
    async def test_invalid_lane_count_defaults_safely(self):
        agent = SwarmManagerAgent()
        res = await agent.execute({"items": [1, 2, 3], "lane_count": "bad"})
        assert res["result"]["route"] == "swarm_parallel"
        assert res["result"]["lane_count"] == 2


class TestMoERouterAgent:
    @pytest.mark.asyncio
    async def test_selects_capability_matching_candidate(self):
        agent = MoERouterAgent()
        res = await agent.execute(
            {
                "required_capability": "FACT_CHECK",
                "candidates": [
                    {"name": "A", "capabilities": ["SUMMARIZE"], "confidence": 0.95, "cost_inr": 0.5},
                    {"name": "B", "capabilities": ["FACT_CHECK"], "confidence": 0.8, "cost_inr": 0.2},
                ],
            }
        )
        assert res["result"]["selected"]["name"] == "B"

    @pytest.mark.asyncio
    async def test_ignores_malformed_candidates(self):
        agent = MoERouterAgent()
        res = await agent.execute(
            {
                "required_capability": "FACT_CHECK",
                "candidates": [
                    "invalid",
                    {"name": "ok", "capabilities": ["FACT_CHECK"], "confidence": "0.7", "cost_inr": "0.4"},
                ],
            }
        )
        assert res["result"]["selected"]["name"] == "ok"


class TestBudgetManagerAgent:
    @pytest.mark.asyncio
    async def test_reserve_and_release(self):
        agent = BudgetManagerAgent()
        reserve = await agent.execute({"action": "reserve", "amount_inr": 10.0})
        assert reserve["result"]["approved"] is True
        assert reserve["result"]["reserved_inr"] == 10.0

        release = await agent.execute({"action": "release", "amount_inr": 4.0})
        assert release["result"]["approved"] is True
        assert release["result"]["reserved_inr"] == 6.0

    @pytest.mark.asyncio
    async def test_invalid_reserve_is_rejected(self):
        agent = BudgetManagerAgent()
        res = await agent.execute({"action": "reserve", "amount_inr": -1})
        assert res["result"]["approved"] is False

    @pytest.mark.asyncio
    async def test_unknown_action_is_rejected(self):
        agent = BudgetManagerAgent()
        res = await agent.execute({"action": "bogus"})
        assert res["result"]["approved"] is False


class TestRouteManagerAgent:
    @pytest.mark.asyncio
    async def test_returns_primary_and_fallbacks(self):
        agent = RouteManagerAgent()
        res = await agent.execute(
            {
                "routes": [
                    {"name": "slow", "confidence": 0.8, "queue_depth": 10, "cost_inr": 0.1},
                    {"name": "best", "confidence": 0.9, "queue_depth": 2, "cost_inr": 0.2},
                    {"name": "cheap", "confidence": 0.7, "queue_depth": 1, "cost_inr": 0.05},
                ]
            }
        )
        assert res["result"]["primary"]["name"] == "best"
        assert len(res["result"]["fallbacks"]) >= 1

    @pytest.mark.asyncio
    async def test_ignores_malformed_routes(self):
        agent = RouteManagerAgent()
        res = await agent.execute(
            {
                "routes": [
                    "invalid",
                    {"name": "valid", "confidence": "0.6", "queue_depth": "3", "cost_inr": "0.2"},
                ]
            }
        )
        assert res["result"]["primary"]["name"] == "valid"
