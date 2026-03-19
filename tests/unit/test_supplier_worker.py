"""Tests for SupplierWorker."""

import pytest
from geosupply.workers.supplier_worker import SupplierWorker, _identify_dependencies, _compute_risk


@pytest.fixture
async def worker():
    w = SupplierWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestSupplierWorkerHelpers:
    def test_identifies_semiconductor_dependency(self):
        deps = _identify_dependencies("We supply semiconductor wafers and chips.")
        assert "SEMICONDUCTOR" in deps

    def test_identifies_pharma_dependency(self):
        deps = _identify_dependencies("API active pharmaceutical ingredient supply.")
        assert "PHARMA" in deps

    def test_identifies_critical_mineral(self):
        deps = _identify_dependencies("lithium and cobalt for battery supply.")
        assert "CRITICAL_MINERAL" in deps

    def test_risk_increases_with_risky_countries(self):
        base = _compute_risk(0.15, ["CN", "RU"], False, False)
        assert base > 0.15

    def test_single_source_adds_penalty(self):
        r1 = _compute_risk(0.15, [], False, False)
        r2 = _compute_risk(0.15, [], True, False)
        assert r2 > r1

    def test_sanctioned_adds_penalty(self):
        r1 = _compute_risk(0.15, [], False, False)
        r2 = _compute_risk(0.15, [], False, True)
        assert r2 > r1

    def test_risk_capped_at_1(self):
        score = _compute_risk(0.90, ["CN", "RU", "KP", "IR"], True, True)
        assert score <= 1.0


class TestSupplierWorkerProcess:
    @pytest.mark.asyncio
    async def test_missing_supplier_id_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "SupplierWorker"

    @pytest.mark.asyncio
    async def test_clean_supplier_low_risk(self, worker):
        res = await worker.process({
            "supplier_id": "ACME_Textiles_IN",
            "description": "Cotton fabric manufacturer in Gujarat.",
            "trace_id": "t-low",
        })
        assert "error_type" not in res
        assert res["result"]["risk_score"] < 0.50

    @pytest.mark.asyncio
    async def test_semiconductor_from_china_high_risk(self, worker):
        res = await worker.process({
            "supplier_id": "SinoChip_SH",
            "description": "Semiconductor wafer fabrication, origin CN.",
            "origin_country": "CN",
            "single_source": True,
            "trace_id": "t-high",
        })
        assert "error_type" not in res
        # base 0.30 + CN penalty 0.15 + single_source 0.20 = 0.65
        assert res["result"]["risk_score"] > 0.50
        assert "SEMICONDUCTOR" in res["result"]["dependencies"]
        assert "CN" in res["result"]["risky_countries"]

    @pytest.mark.asyncio
    async def test_sanctioned_flag_boosts_risk(self, worker):
        res = await worker.process({
            "supplier_id": "SomeCo",
            "description": "General trading company.",
            "sanctioned": True,
            "trace_id": "t-sanc",
        })
        assert res["result"]["risk_score"] >= 0.35

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, worker):
        res = await worker.process({
            "supplier_id": "TestCo",
            "description": "Steel manufacturer.",
            "trace_id": "t-fields",
        })
        r = res["result"]
        for f in ("supplier_id", "risk_score", "dependencies", "risky_countries"):
            assert f in r

    @pytest.mark.asyncio
    async def test_meta_fields(self, worker):
        res = await worker.process({
            "supplier_id": "TestCo",
            "trace_id": "t-meta",
        })
        assert res["meta"]["worker"] == "SupplierWorker"
        assert res["meta"]["tier"] == 1
        assert res["meta"]["cost_inr"] == 0.0


class TestSupplierWorkerMeta:
    def test_capabilities(self):
        w = SupplierWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "SUPPLIER_SCORE" in caps["capabilities"]
