"""Tests for FastAPI REST API routers (test_api_routers.py).

Uses httpx.AsyncClient + ASGITransport to test all 8 router modules.
All dependency singletons are overridden via app.dependency_overrides so no
real external services are hit.
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
# Helpers
# ---------------------------------------------------------------------------

def _make_swarm_master() -> SwarmMaster:
    """Return a SwarmMaster with all 14 real supervisor stubs registered."""
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
    return sm


def _make_app(task_store: dict | None = None):
    """Create a test-scoped FastAPI app with overridden dependencies."""
    app = create_app()
    sm = _make_swarm_master()
    budget_agent = BudgetManagerAgent()
    store = task_store if task_store is not None else {}

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
# TestHealthEndpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_liveness_returns_ok(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/health")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "environment" in data
        assert "timestamp" in data

    def test_deep_health_returns_ok(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/health/deep")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["supervisors_registered"] == 14
        assert data["workers_count"] >= 0
        assert data["agents_count"] >= 0

    def test_deep_health_budget_remaining_is_float(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/health/deep")

        resp = asyncio.run(_run())
        data = resp.json()
        assert isinstance(data["budget_remaining_inr"], float)


# ---------------------------------------------------------------------------
# TestAuditEndpoints
# ---------------------------------------------------------------------------

class TestAuditEndpoints:
    def test_audit_status_returns_counts(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/audit")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        for key in ("workers_discovered", "agents_discovered", "subagents_discovered", "schema_count"):
            assert key in data
            assert isinstance(data[key], int)

    def test_audit_run_returns_passed_failed(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/audit/run")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "passed" in data
        assert "failed" in data
        assert "categories_run" in data
        assert isinstance(data["categories_run"], list)

    def test_audit_run_custom_categories(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/audit/run?categories=breakage&level=strict")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "breakage" in data["categories_run"]

    def test_audit_run_sets_last_run_at(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.get("/audit/run")
                return await client.get("/audit")

        resp = asyncio.run(_run())
        data = resp.json()
        # last_run_at should now be populated after /audit/run
        assert data["last_run_at"] is not None


# ---------------------------------------------------------------------------
# TestWorkersEndpoints
# ---------------------------------------------------------------------------

class TestWorkersEndpoints:
    def test_workers_list_returns_list(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/workers")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "workers" in data
        assert isinstance(data["workers"], list)
        assert data["count"] == len(data["workers"])

    def test_agents_list_returns_list(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/agents")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert data["count"] == len(data["agents"])

    def test_supervisors_list_returns_list(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/supervisors")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "supervisors" in data
        assert data["count"] >= 14  # At least all 14 supervisor subclasses registered


# ---------------------------------------------------------------------------
# TestBudgetEndpoints
# ---------------------------------------------------------------------------

class TestBudgetEndpoints:
    def test_budget_status_returns_valid_schema(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/budget")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["cap_inr"] == 500.0
        assert data["alert_level"] in ("NORMAL", "WARN", "ALERT", "CRITICAL")
        assert "reserved_inr" in data
        assert "remaining_inr" in data

    def test_budget_history_returns_list(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/budget/history")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "count" in data
        assert isinstance(data["history"], list)


# ---------------------------------------------------------------------------
# TestTaskEndpoints
# ---------------------------------------------------------------------------

class TestTaskEndpoints:
    def test_submit_task_returns_202(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] in ("queued", "rejected")
        assert data["supervisor"] == "IngestionSupervisor"

    def test_submit_task_budget_over_500_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "budget_inr": 501.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_submit_task_budget_zero_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "budget_inr": 0.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_submit_task_invalid_priority_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "priority": "P9", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_get_task_status_after_submit(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                submit = await client.post(
                    "/tasks",
                    json={"task_type": "INGEST_NEWS", "budget_inr": 5.0},
                )
                task_id = submit.json()["task_id"]
                return await client.get(f"/tasks/{task_id}")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] in ("completed", "pending", "running", "error", "rejected", "skipped")

    def test_get_task_status_unknown_returns_404(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/tasks/no-such-task-id-xyz")

        resp = asyncio.run(_run())
        assert resp.status_code == 404

    def test_submit_unknown_task_type_routes_to_ingestion(self):
        """Unknown task_types fall back to IngestionSupervisor."""
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/tasks",
                    json={"task_type": "TOTALLY_UNKNOWN_TASK_XYZ", "budget_inr": 5.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 202
        assert resp.json()["supervisor"] == "IngestionSupervisor"


# ---------------------------------------------------------------------------
# TestPipelineEndpoints
# ---------------------------------------------------------------------------

class TestPipelineEndpoints:
    def test_pipeline_status_for_existing_task(self):
        store = {
            "test-task-001": {
                "task_id": "test-task-001",
                "status": "completed",
                "result": {"data": "ok"},
                "cost_inr": 0.5,
            }
        }
        app, _ = _make_app(task_store=store)

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/pipeline/test-task-001")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "test-task-001"
        assert data["status"] == "completed"
        assert data["cost_inr"] == 0.5

    def test_pipeline_status_unknown_task_returns_404(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/pipeline/no-such-task-999")

        resp = asyncio.run(_run())
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestBriefEndpoint
# ---------------------------------------------------------------------------

class TestBriefEndpoint:
    def test_brief_with_empty_payload_returns_200(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post("/brief", json={"payload": {}, "budget_inr": 50.0})

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert "plan_id" in data
        assert "task_results" in data
        assert "total_cost_inr" in data
        assert isinstance(data["task_results"], dict)

    def test_brief_with_region_payload(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/brief",
                    json={"payload": {"region": "INDIA"}, "budget_inr": 50.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] is not None
        # 10 tasks in SUPPLY_BRIEF_TEMPLATE
        assert len(data["task_results"]) == 10

    def test_brief_with_custom_plan_id(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/brief",
                    json={"payload": {}, "plan_id": "my-plan-001", "budget_inr": 50.0},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == "my-plan-001"

    def test_brief_budget_negative_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post("/brief", json={"payload": {}, "budget_inr": -1.0})

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_brief_total_cost_is_float(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post("/brief", json={"payload": {}, "budget_inr": 50.0})

        resp = asyncio.run(_run())
        data = resp.json()
        assert isinstance(data["total_cost_inr"], float)


# ---------------------------------------------------------------------------
# TestKGEndpoints
# ---------------------------------------------------------------------------

class TestKGEndpoints:
    def test_kg_query_valid(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/kg/query?entity=India&depth=1")

        resp = asyncio.run(_run())
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity"] == "India"
        assert "triples" in data
        assert "node_count" in data

    def test_kg_query_depth_zero_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/kg/query?entity=India&depth=0")

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_kg_query_depth_four_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/kg/query?entity=India&depth=4")

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_kg_query_missing_entity_returns_422(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.get("/kg/query?depth=1")

        resp = asyncio.run(_run())
        assert resp.status_code == 422

    def test_kg_update_creates_triple(self):
        app, _ = _make_app()

        async def _run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(
                    "/kg/update",
                    json={"subject": "India", "predicate": "exports", "object": "rice"},
                )

        resp = asyncio.run(_run())
        assert resp.status_code == 201
        assert resp.json()["status"] == "created"
