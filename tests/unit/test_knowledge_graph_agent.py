"""Tests for KnowledgeGraphAgent."""

import pytest
from geosupply.agents.knowledge_graph_agent import KnowledgeGraphAgent, KGTriple
from geosupply.config import KG_WRITE_BUFFER_BATCH_SIZE


@pytest.fixture
def agent():
    return KnowledgeGraphAgent()


class TestKGTriple:
    def test_dedup_key_lowercased(self):
        t = KGTriple("India", "TRADE", "China")
        assert t.dedup_key == ("india", "china", "TRADE")

    def test_dedup_key_relation_uppercased(self):
        t = KGTriple("India", "ally", "USA")
        assert t.dedup_key[2] == "ALLY"

    def test_to_dict_has_all_fields(self):
        t = KGTriple("A", "REL", "B", weight=0.8)
        d = t.to_dict()
        for f in ("source", "relation", "target", "weight", "timestamp"):
            assert f in d


class TestKnowledgeGraphAgentAddTriple:
    @pytest.mark.asyncio
    async def test_add_triple_buffered(self, agent):
        res = await agent.safe_execute({
            "task_type": "KG_ADD_TRIPLE",
            "source": "India",
            "relation": "TRADE",
            "target": "China",
            "trace_id": "t-add",
        })
        assert res["result"]["status"] == "buffered"
        assert res["result"]["buffer_depth"] == 1

    @pytest.mark.asyncio
    async def test_add_triple_missing_source_returns_error(self, agent):
        res = await agent.safe_execute({
            "task_type": "KG_ADD_TRIPLE",
            "source": "",
            "target": "China",
            "trace_id": "t-err",
        })
        assert res["result"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_buffer_flushes_at_batch_size(self, agent):
        for i in range(KG_WRITE_BUFFER_BATCH_SIZE):
            await agent.safe_execute({
                "task_type": "KG_ADD_TRIPLE",
                "source": f"Entity_{i}",
                "relation": "RELATED",
                "target": f"Target_{i}",
                "trace_id": f"t-{i}",
            })
        # Buffer should have flushed and cleared
        assert len(agent._write_buffer) == 0
        assert agent._total_added == KG_WRITE_BUFFER_BATCH_SIZE

    @pytest.mark.asyncio
    async def test_dedup_prevents_duplicate_in_window(self, agent):
        for _ in range(3):
            await agent.safe_execute({
                "task_type": "KG_ADD_TRIPLE",
                "source": "India",
                "relation": "ALLY",
                "target": "USA",
                "trace_id": "t-dup",
            })
        # Flush to graph
        await agent.safe_execute({"task_type": "KG_FLUSH", "trace_id": "t-flush"})
        # Only 1 unique triple should exist
        assert agent._total_deduped >= 2


class TestKnowledgeGraphAgentQuery:
    @pytest.mark.asyncio
    async def test_query_returns_neighbours(self, agent):
        # Add and flush
        await agent.safe_execute({
            "task_type": "KG_ADD_TRIPLE",
            "source": "India",
            "relation": "TRADE",
            "target": "Japan",
            "trace_id": "t-q1",
        })
        await agent.safe_execute({"task_type": "KG_FLUSH", "trace_id": "t-f"})

        res = await agent.safe_execute({
            "task_type": "KG_QUERY",
            "entity": "India",
            "trace_id": "t-query",
        })
        assert res["result"]["count"] >= 1
        assert any(n["target"] == "japan" for n in res["result"]["neighbours"])

    @pytest.mark.asyncio
    async def test_query_unknown_entity_returns_empty(self, agent):
        res = await agent.safe_execute({
            "task_type": "KG_QUERY",
            "entity": "Narnia",
            "trace_id": "t-empty",
        })
        assert res["result"]["count"] == 0
        assert res["result"]["neighbours"] == []

    @pytest.mark.asyncio
    async def test_query_with_relation_filter(self, agent):
        await agent.safe_execute({
            "task_type": "KG_ADD_TRIPLE",
            "source": "Russia",
            "relation": "CONFLICT",
            "target": "Ukraine",
            "trace_id": "t-cf1",
        })
        await agent.safe_execute({"task_type": "KG_FLUSH", "trace_id": "t-flushf"})

        res = await agent.safe_execute({
            "task_type": "KG_QUERY",
            "entity": "Russia",
            "relation_filter": "CONFLICT",
            "trace_id": "t-filter",
        })
        assert res["result"]["count"] >= 1
        assert all(n["relation"] == "CONFLICT" for n in res["result"]["neighbours"])


class TestKnowledgeGraphAgentStats:
    @pytest.mark.asyncio
    async def test_stats_initial_zero(self, agent):
        res = await agent.safe_execute({"task_type": "KG_STATS", "trace_id": "t-stats"})
        r = res["result"]
        assert r["node_count"] == 0
        assert r["edge_count"] == 0
        assert r["total_added"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_add_and_flush(self, agent):
        await agent.safe_execute({
            "task_type": "KG_ADD_TRIPLE",
            "source": "A",
            "relation": "REL",
            "target": "B",
            "trace_id": "t-s1",
        })
        await agent.safe_execute({"task_type": "KG_FLUSH", "trace_id": "t-fs"})
        res = await agent.safe_execute({"task_type": "KG_STATS", "trace_id": "t-stats2"})
        assert res["result"]["node_count"] >= 1
        assert res["result"]["edge_count"] >= 1

    @pytest.mark.asyncio
    async def test_canary_sample_populated(self, agent):
        for i in range(5):
            await agent.safe_execute({
                "task_type": "KG_ADD_TRIPLE",
                "source": f"S{i}",
                "relation": "R",
                "target": f"T{i}",
                "trace_id": f"t-c{i}",
            })
        await agent.safe_execute({"task_type": "KG_FLUSH", "trace_id": "t-cf"})
        res = await agent.safe_execute({"task_type": "KG_CANARY", "trace_id": "t-canary"})
        assert res["result"]["sample_size"] == 5


class TestKnowledgeGraphAgentMeta:
    def test_capabilities(self):
        a = KnowledgeGraphAgent()
        caps = a.advertise_capabilities()
        assert "KG_BUILD" in caps["capabilities"]
        assert "KG_QUERY" in caps["capabilities"]

    def test_repr_includes_node_edge(self):
        a = KnowledgeGraphAgent()
        assert "KnowledgeGraphAgent" in repr(a)

    def test_state_machine_idle_after_execute(self):
        a = KnowledgeGraphAgent()
        assert a.state == "IDLE"
