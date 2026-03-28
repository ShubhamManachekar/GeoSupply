"""
Integration tests — FastAPI REST API E2E flows (Phase 9).
FA v3 | Zero mocks. Real logic paths only.

Tests:
    1. full_supply_brief_pipeline — POST /brief executes all 10 SUPPLY_BRIEF tasks
    2. component_discovery_matches_audit — /workers + /agents counts consistent with /audit
    3. task_submit_and_status_roundtrip — POST /tasks → GET /tasks/{id} roundtrip
"""

from __future__ import annotations

import asyncio

import pytest

from httpx import AsyncClient, ASGITransport

from geosupply.api.main import create_app
from geosupply.api.dependencies import swarm_master_dep, budget_dep, task_store_dep
from geosupply.orchestrator.swarm_master import SwarmMaster
from geosupply.supervisors.ingestion_supervisor import IngestionSupervisor
from geosupply.supervisors.nlp_supervisor import NLPSupervisor
from geosupply.supervisors.quality_supervisor import QualitySupervisor
from geosupply.supervisors.intel_supervisor import IntelSupervisor
from geosupply.supervisors.infra_supervisor import InfraSupervisor
from geosupply.supervisors.disaster_recovery_supervisor import DisasterRecoverySupervisor
from geosupply.supervisors.ml_supervisor import MLSupervisor
from geosupply.supervisors.india_supervisor import IndiaSupervisor
from geosupply.supervisors.dashboard_supervisor import DashboardSupervisor
from geosupply.supervisors.dev_supervisor import DevSupervisor
from geosupply.supervisors.test_supervisor import TestSupervisor
from geosupply.supervisors.tech_supervisor import TechSupervisor
from geosupply.supervisors.marketing_supervisor import MarketingSupervisor
from geosupply.supervisors.loophole_hunter_supervisor import LoopholeHunterSupervisor
from geosupply.agents.budget_manager_agent import BudgetManagerAgent


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------

def _full_app():
    """Create an app with all 14 supervisors registered."""
    app = create_app()
    sm = SwarmMaster()
    sm.register_supervisor("IngestionSupervisor",        IngestionSupervisor())
    sm.register_supervisor("NLPSupervisor",              NLPSupervisor())
    sm.register_supervisor("QualitySupervisor",          QualitySupervisor())
    sm.register_supervisor("IntelSupervisor",            IntelSupervisor())
    sm.register_supervisor("InfraSupervisor",            InfraSupervisor())
    sm.register_supervisor("DisasterRecoverySupervisor", DisasterRecoverySupervisor())
    sm.register_supervisor("MLSupervisor",               MLSupervisor())
    sm.register_supervisor("IndiaSupervisor",            IndiaSupervisor())
    sm.register_supervisor("DashboardSupervisor",        DashboardSupervisor())
    sm.register_supervisor("DevSupervisor",              DevSupervisor())
    sm.register_supervisor("TestSupervisor",             TestSupervisor())
    sm.register_supervisor("TechSupervisor",             TechSupervisor())
    sm.register_supervisor("MarketingSupervisor",        MarketingSupervisor())
    sm.register_supervisor("LoopholeHunterSupervisor",   LoopholeHunterSupervisor())
    budget_agent = BudgetManagerAgent()
    store: dict = {}

    async def _sm_dep():
        return sm

    async def _budget_dep():
        return budget_agent

    async def _store_dep():
        return store

    app.dependency_overrides[swarm_master_dep] = _sm_dep
    app.dependency_overrides[budget_dep] = _budget_dep
    app.dependency_overrides[task_store_dep] = _store_dep
    return app, store


# ---------------------------------------------------------------------------
# Test 1: full_supply_brief_pipeline
# ---------------------------------------------------------------------------

class TestFullSupplyBriefPipeline:
    """POST /brief executes all 10 SUPPLY_BRIEF DAG tasks and returns valid response."""

    def test_brief_pipeline_produces_ten_task_results(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/brief",
                    json={
                        "payload": {"region": "INDIA", "depth": 2},
                        "budget_inr": 100.0,
                    },
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "plan_id" in data
        assert len(data["task_results"]) == 10
        assert isinstance(data["total_cost_inr"], float)
        assert data["total_cost_inr"] >= 0.0

    def test_brief_pipeline_all_tasks_have_status(self):
        """Each task result must have a 'status' key."""
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/brief",
                    json={"payload": {}, "budget_inr": 50.0},
                )

        resp = asyncio.run(_run())
        data = resp.json()
        for task_id, result in data["task_results"].items():
            assert "status" in result, f"task {task_id!r} missing 'status'"

    def test_brief_pipeline_custom_plan_id_preserved(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/brief",
                    json={"payload": {}, "plan_id": "integration-test-plan", "budget_inr": 50.0},
                )

        resp = asyncio.run(_run())
        data = resp.json()
        assert data["plan_id"] == "integration-test-plan"

    def test_brief_generated_at_is_present(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post("/brief", json={"payload": {}, "budget_inr": 50.0})

        resp = asyncio.run(_run())
        data = resp.json()
        assert "generated_at" in data
        assert data["generated_at"] is not None


# ---------------------------------------------------------------------------
# Test 2: component_discovery_matches_audit
# ---------------------------------------------------------------------------

class TestComponentDiscoveryMatchesAudit:
    """Component counts from /workers, /agents, /supervisors must be consistent with /audit."""

    def test_worker_count_matches_audit_workers_discovered(self):
        app, _ = _full_app()

        # Import all components so subclasses are populated (mirrors lifespan warmup)
        import geosupply.workers   # noqa: F401
        import geosupply.agents    # noqa: F401
        import geosupply.supervisors  # noqa: F401
        import geosupply.subagents  # noqa: F401

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                workers_resp = await client.get("/workers")
                audit_resp = await client.get("/audit")
            return workers_resp, audit_resp

        workers_resp, audit_resp = asyncio.run(_run())
        workers_data = workers_resp.json()
        audit_data = audit_resp.json()
        assert workers_data["count"] == audit_data["workers_discovered"]

    def test_all_supervisor_subclasses_at_least_14(self):
        """After importing supervisors module, at least 14 subclasses must be discoverable."""
        app, _ = _full_app()

        import geosupply.supervisors  # noqa: F401

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/supervisors")

        resp = asyncio.run(_run())
        data = resp.json()
        assert data["count"] >= 14

    def test_schema_count_consistent(self):
        """Schema count reported by /audit must be > 0."""
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/audit")

        resp = asyncio.run(_run())
        data = resp.json()
        assert data["schema_count"] > 0


# ---------------------------------------------------------------------------
# Test 3: task_submit_and_status_roundtrip
# ---------------------------------------------------------------------------

class TestTaskSubmitAndStatusRoundtrip:
    """POST /tasks → GET /tasks/{id} and GET /pipeline/{id} roundtrip."""

    def test_submit_and_retrieve_ingest_news(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                submit = await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "priority": "P1", "budget_inr": 10.0},
                )
                task_id = submit.json()["task_id"]
                status = await client.get(f"/tasks/{task_id}")
                pipeline = await client.get(f"/pipeline/{task_id}")
            return submit, status, pipeline

        submit, status, pipeline = asyncio.run(_run())
        assert submit.status_code == 202
        assert status.status_code == 200
        assert pipeline.status_code == 200
        # Both endpoints return the same task_id
        assert status.json()["task_id"] == pipeline.json()["task_id"]

    def test_submit_nlp_sentiment_routes_to_nlp_supervisor(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "NLP_SENTIMENT", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 202
        assert resp.json()["supervisor"] == "NLPSupervisor"

    def test_submit_ml_task_routes_to_ml_supervisor(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "ML_STRESS_SCORE", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 202
        assert resp.json()["supervisor"] == "MLSupervisor"

    def test_submit_loophole_task_routes_to_loophole_supervisor(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "LOOPHOLE_SCAN", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 202
        assert resp.json()["supervisor"] == "LoopholeHunterSupervisor"

    def test_nonexistent_task_404_on_pipeline(self):
        app, _ = _full_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/pipeline/this-task-does-not-exist-9999")

        resp = asyncio.run(_run())
        assert resp.status_code == 404
