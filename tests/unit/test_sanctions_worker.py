"""Tests for SanctionsWorker."""

import pytest
from geosupply.workers.sanctions_worker import SanctionsWorker


@pytest.fixture
async def worker():
    w = SanctionsWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestSanctionsWorkerProcess:
    @pytest.mark.asyncio
    async def test_detects_iran_sanctions(self, worker):
        res = await worker.process({
            "entity_name": "IRGC Quds Force",
            "trace_id": "t-iran",
        })
        assert "error_type" not in res
        assert res["result"]["is_sanctioned"] is True
        assert "OFAC" in res["result"]["sanctioned_by"]

    @pytest.mark.asyncio
    async def test_detects_north_korea(self, worker):
        res = await worker.process({
            "entity_name": "Lazarus Group DPRK",
            "trace_id": "t-kp",
        })
        assert res["result"]["is_sanctioned"] is True
        assert "UN" in res["result"]["sanctioned_by"]

    @pytest.mark.asyncio
    async def test_detects_russia_sectoral(self, worker):
        res = await worker.process({
            "entity_name": "Gazprom",
            "trace_id": "t-ru",
        })
        assert res["result"]["is_sanctioned"] is True
        assert "EU" in res["result"]["sanctioned_by"]

    @pytest.mark.asyncio
    async def test_detects_terrorist_group(self, worker):
        res = await worker.process({
            "entity_name": "Hamas militant wing",
            "trace_id": "t-hamas",
        })
        assert res["result"]["is_sanctioned"] is True
        assert "India_MEA" in res["result"]["sanctioned_by"]

    @pytest.mark.asyncio
    async def test_clean_entity_not_sanctioned(self, worker):
        res = await worker.process({
            "entity_name": "Tata Steel Limited",
            "trace_id": "t-clean",
        })
        assert "error_type" not in res
        assert res["result"]["is_sanctioned"] is False
        assert res["result"]["sanctioned_by"] == []

    @pytest.mark.asyncio
    async def test_context_field_used_for_screening(self, worker):
        res = await worker.process({
            "entity_name": "Unknown Trading Co",
            "context": "operates in North Korea DPRK",
            "trace_id": "t-ctx",
        })
        assert res["result"]["is_sanctioned"] is True

    @pytest.mark.asyncio
    async def test_missing_entity_name_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "SanctionsWorker"

    @pytest.mark.asyncio
    async def test_result_has_screening_bodies(self, worker):
        res = await worker.process({
            "entity_name": "TestEntity",
            "trace_id": "t-bodies",
        })
        assert "screening_bodies" in res["result"]
        assert "OFAC" in res["result"]["screening_bodies"]

    @pytest.mark.asyncio
    async def test_sanction_type_populated_when_hit(self, worker):
        res = await worker.process({
            "entity_name": "Wagner Group",
            "trace_id": "t-type",
        })
        assert res["result"]["is_sanctioned"] is True
        assert res["result"]["sanction_type"] != ""


class TestSanctionsWorkerMeta:
    def test_capabilities(self):
        w = SanctionsWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "SANCTIONS_CHECK" in caps["capabilities"]
        assert "ENTITY_SCREEN" in caps["capabilities"]
