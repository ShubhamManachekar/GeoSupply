"""Tests for SourceCredWorker."""

import pytest

from geosupply.workers.source_cred_worker import SourceCredWorker, _extract_domain, _base_score


@pytest.fixture
async def worker():
    w = SourceCredWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestSourceCredHelpers:
    def test_extract_domain_from_url(self):
        assert _extract_domain("https://www.reuters.com/article/123") == "reuters.com"

    def test_extract_domain_bare(self):
        assert _extract_domain("bbc.com") == "bbc.com"

    def test_extract_domain_gov(self):
        assert _extract_domain("https://dgft.gov.in/data") == "dgft.gov.in"

    def test_base_score_high_cred(self):
        assert _base_score("reuters.com") == 0.85

    def test_base_score_gov_in(self):
        assert _base_score("dgft.gov.in") == 0.90

    def test_base_score_unknown(self):
        assert _base_score("randomsite.xyz") == 0.55


class TestSourceCredWorkerProcess:
    @pytest.mark.asyncio
    async def test_high_cred_domain_scores_well(self, worker):
        res = await worker.process({
            "source_id": "https://reuters.com/article/foo",
            "trace_id": "t-hc",
        })
        assert "error_type" not in res
        assert res["result"]["credibility_score"] >= 0.80
        assert res["result"]["domain"] == "reuters.com"

    @pytest.mark.asyncio
    async def test_gov_domain_scores_high(self, worker):
        res = await worker.process({
            "source_id": "https://mospi.gov.in/data",
            "trace_id": "t-gov",
        })
        assert "error_type" not in res
        assert res["result"]["credibility_score"] >= 0.85

    @pytest.mark.asyncio
    async def test_missing_source_id_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "SourceCredWorker"

    @pytest.mark.asyncio
    async def test_empty_source_id_returns_error(self, worker):
        res = await worker.process({"source_id": "   ", "trace_id": "t-empty"})
        assert res["error_type"] == "INPUT_INVALID"

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, worker):
        res = await worker.process({
            "source_id": "apnews.com",
            "trace_id": "t-fields",
        })
        assert "error_type" not in res
        result = res["result"]
        assert "credibility_score" in result
        assert "source_id" in result
        assert "domain" in result
        assert "permanently_flagged" in result
        assert "strike_count" in result

    @pytest.mark.asyncio
    async def test_meta_fields_present(self, worker):
        res = await worker.process({
            "source_id": "thehindu.com",
            "trace_id": "t-meta",
        })
        assert res["meta"]["worker"] == "SourceCredWorker"
        assert res["meta"]["tier"] == 1
        assert res["meta"]["cost_inr"] == 0.0


class TestSourceCredWorkerMeta:
    def test_capabilities(self):
        w = SourceCredWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "SOURCE_SCORE" in caps["capabilities"]
        assert "CREDIBILITY" in caps["capabilities"]
