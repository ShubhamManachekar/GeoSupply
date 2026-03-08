"""Tests for NERWorker."""

import pytest

from geosupply.workers.ner_worker import NERWorker


@pytest.fixture
async def worker():
    w = NERWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestNERWorkerProcess:
    @pytest.mark.asyncio
    async def test_extracts_gpe_org_and_person_entities(self, worker):
        text = "India and China held talks at UN headquarters with John Miller from RBI."
        res = await worker.process({"text": text, "trace_id": "t-ner"})
        assert "error_type" not in res

        entities = res["result"]["entities"]
        texts = {entity["text"] for entity in entities}
        labels = {entity["entity_type"] for entity in entities}

        assert "India" in texts
        assert "China" in texts
        assert "UN" in texts
        assert "PERSON" in labels
        assert "ORG" in labels
        assert "GPE" in labels

    @pytest.mark.asyncio
    async def test_returns_empty_entities_for_neutral_text(self, worker):
        res = await worker.process({"text": "supply chain resilience requires planning", "trace_id": "t-empty"})
        assert "error_type" not in res
        assert res["result"]["entities"] == []

    @pytest.mark.asyncio
    async def test_missing_text_returns_worker_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "NERWorker"


class TestNERWorkerMeta:
    def test_capabilities(self):
        w = NERWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 1
        assert caps["use_static"] is True
        assert "NER_EXTRACT" in caps["capabilities"]
