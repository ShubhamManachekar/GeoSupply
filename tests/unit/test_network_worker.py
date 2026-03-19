"""Tests for NetworkWorker."""

import pytest
from geosupply.workers.network_worker import NetworkWorker, _extract_entities, _detect_relations


@pytest.fixture
async def worker():
    w = NetworkWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestNetworkWorkerHelpers:
    def test_extracts_known_gpe(self):
        entities = _extract_entities("India and China held trade talks.")
        assert "India" in entities
        assert "China" in entities

    def test_detects_conflict_relation(self):
        rels = _detect_relations("Russia invaded Ukraine in a major conflict.")
        assert "CONFLICT" in rels

    def test_detects_trade_relation(self):
        rels = _detect_relations("India exports software to the USA.")
        assert "TRADE" in rels

    def test_detects_ally_relation(self):
        rels = _detect_relations("India and USA are strong allies in the Indo-Pacific alliance.")
        assert "ALLY" in rels

    def test_detects_diplomatic_relation(self):
        rels = _detect_relations("Negotiating a peace treaty through diplomatic talks.")
        assert "DIPLOMATIC" in rels


class TestNetworkWorkerProcess:
    @pytest.mark.asyncio
    async def test_happy_path_extracts_entities_and_relations(self, worker):
        text = "India and China held talks. Russia supplied weapons during the conflict."
        res = await worker.process({"text": text, "trace_id": "t-net"})
        assert "error_type" not in res
        assert res["result"]["node_count"] >= 2
        assert len(res["result"]["relations"]) >= 1

    @pytest.mark.asyncio
    async def test_edges_built_between_entity_pairs(self, worker):
        text = "India and Pakistan have ongoing conflict and trade disputes."
        res = await worker.process({"text": text, "trace_id": "t-edges"})
        assert res["result"]["edge_count"] >= 1
        assert len(res["result"]["edges"]) >= 1

    @pytest.mark.asyncio
    async def test_clusters_produced(self, worker):
        text = "India, China and Russia are forming trade alliances."
        res = await worker.process({"text": text, "trace_id": "t-cluster"})
        assert len(res["result"]["clusters"]) >= 1
        assert res["result"]["clusters"][0]["size"] >= 2

    @pytest.mark.asyncio
    async def test_missing_text_returns_error(self, worker):
        res = await worker.process({"trace_id": "t-err"})
        assert res["error_type"] == "INPUT_INVALID"
        assert res["worker_name"] == "NetworkWorker"

    @pytest.mark.asyncio
    async def test_sanitised_text_preferred(self, worker):
        res = await worker.process({
            "text": "nothing",
            "sanitised_text": "India and China are trade partners.",
            "trace_id": "t-san",
        })
        assert "error_type" not in res
        assert "India" in res["result"]["entities"]

    @pytest.mark.asyncio
    async def test_result_fields_complete(self, worker):
        res = await worker.process({
            "text": "India holds diplomatic talks with Russia.",
            "trace_id": "t-fields",
        })
        r = res["result"]
        for f in ("entities", "relations", "clusters", "edges", "node_count", "edge_count"):
            assert f in r

    @pytest.mark.asyncio
    async def test_edges_capped_at_20(self, worker):
        # many entities → many edges, but cap at 20
        text = " ".join([
            "India China Russia Ukraine Pakistan USA Iran Israel Taiwan Saudi Arabia NATO Europe"
        ])
        res = await worker.process({"text": text, "trace_id": "t-cap"})
        assert len(res["result"]["edges"]) <= 20


class TestNetworkWorkerMeta:
    def test_capabilities(self):
        w = NetworkWorker()
        caps = w.advertise_capabilities()
        assert caps["tier"] == 2
        assert caps["use_static"] is False
        assert "NARRATIVE_NETWORK" in caps["capabilities"]
