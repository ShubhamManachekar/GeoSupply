"""
Freemium plan-gating tests (FREE / PRO / ENTERPRISE). Real router, real
gate; plan switched via the GEOSUPPLY_PLAN env var exactly as in production.
"""
from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from geosupply.osint.plans import (
    FEATURE_MIN_PLAN,
    PLAN_ORDER,
    current_plan,
    has_feature,
    plan_info,
)


class TestPlanModel:
    def test_default_is_enterprise_self_hosted(self, monkeypatch):
        monkeypatch.delenv("GEOSUPPLY_PLAN", raising=False)
        assert current_plan() == "ENTERPRISE"
        assert plan_info().locked == []       # self-hosted is never crippled

    def test_invalid_plan_falls_back_to_enterprise(self, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "PLATINUM")
        assert current_plan() == "ENTERPRISE"

    def test_feature_ladder(self, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "FREE")
        assert has_feature("dashboard")
        assert not has_feature("advanced_intel")
        assert not has_feature("swarm")
        monkeypatch.setenv("GEOSUPPLY_PLAN", "PRO")
        assert has_feature("advanced_intel")
        assert not has_feature("swarm")
        monkeypatch.setenv("GEOSUPPLY_PLAN", "ENTERPRISE")
        assert all(has_feature(f) for f in FEATURE_MIN_PLAN)

    def test_unknown_feature_always_locked(self):
        assert not has_feature("teleportation")

    def test_upgrade_hint_prices_in_inr(self, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "FREE")
        info = plan_info()
        assert "₹499" in info.upgrade_hint    # INR, never USD (project rule)
        assert info.price_inr == 0
        assert set(info.locked) == {"advanced_intel", "swarm"}

    def test_plan_order_is_a_ladder(self):
        assert PLAN_ORDER == ("FREE", "PRO", "ENTERPRISE")


@pytest.fixture
async def api(tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_STATE_PATH", str(tmp_path / "learn.json"))
    from geosupply.api.main import create_app
    from geosupply.api.routers import osint as osint_module
    from geosupply.osint.aggregator import OsintAggregator

    agg = OsintAggregator(client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
    app = create_app()
    app.dependency_overrides[osint_module.aggregator_dep] = lambda: agg
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        yield client
    app.dependency_overrides.clear()
    await agg.teardown()


class TestPlanGates:
    async def test_free_keeps_dashboard_blocks_pro_features(self, api, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "FREE")
        assert (await api.get("/osint/snapshot")).status_code == 200
        assert (await api.get("/osint/warzones")).status_code == 200
        assert (await api.get("/osint/streams")).status_code == 200
        resp = await api.get("/osint/ask", params={"q": "hormuz"})
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["required_plan"] == "PRO"
        assert detail["price_inr"] == 499
        assert (await api.get("/osint/graph")).status_code == 403
        assert (await api.post("/osint/ask/feedback", json={"items": []})).status_code == 403

    async def test_pro_unlocks_intel_blocks_swarm(self, api, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "PRO")
        assert (await api.get("/osint/ask", params={"q": "hormuz"})).status_code == 200
        assert (await api.get("/osint/graph")).status_code == 200
        resp = await api.get("/budget/status")
        assert resp.status_code in (403, 404)  # gated before routing details
        if resp.status_code == 403:
            assert resp.json()["detail"]["required_plan"] == "ENTERPRISE"

    async def test_enterprise_unlocks_everything(self, api, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "ENTERPRISE")
        assert (await api.get("/osint/ask", params={"q": "hormuz"})).status_code == 200
        info = (await api.get("/osint/plan")).json()
        assert info["plan"] == "ENTERPRISE" and info["locked"] == []

    async def test_plan_endpoint_reflects_env(self, api, monkeypatch):
        monkeypatch.setenv("GEOSUPPLY_PLAN", "FREE")
        info = (await api.get("/osint/plan")).json()
        assert info["plan"] == "FREE"
        assert "advanced_intel" in info["locked"]
        assert "PRO" in info["upgrade_hint"]
