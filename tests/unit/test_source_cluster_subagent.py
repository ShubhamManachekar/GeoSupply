"""Tests for SourceClusterSubAgent — coordinated source detection."""

import pytest
from geosupply.subagents.source_cluster_subagent import (
    SourceClusterSubAgent,
    _extract_domain,
    _style_overlap,
    _cluster_sources,
    STYLE_CLUSTER_THRESHOLD,
)


@pytest.fixture
async def subagent():
    s = SourceClusterSubAgent()
    await s.setup()
    yield s
    await s.teardown()


class TestHelpers:
    def test_extract_domain_with_prefix(self):
        assert _extract_domain("src:thehindu.com") == "thehindu.com"

    def test_extract_domain_plain(self):
        assert _extract_domain("ndtv.com") == "ndtv.com"

    def test_extract_domain_subdomain(self):
        assert _extract_domain("src:news.thehindu.com") == "thehindu.com"

    def test_style_overlap_identical(self):
        assert _style_overlap(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_style_overlap_zero(self):
        assert _style_overlap(["a", "b"], ["x", "y"]) == 0.0

    def test_style_overlap_empty(self):
        assert _style_overlap([], ["a"]) == 0.0

    def test_style_overlap_partial(self):
        overlap = _style_overlap(["a", "b", "c"], ["a", "b", "d"])
        assert 0.0 < overlap < 1.0


class TestClustering:
    def test_same_domain_clusters_together(self):
        sources = [
            {"source_id": "src:thehindu.com"},
            {"source_id": "src:news.thehindu.com"},
        ]
        clusters = _cluster_sources(sources)
        # Both should be in same cluster
        all_members = [m for members in clusters.values() for m in members]
        assert len(set(all_members)) == 2
        assert len(clusters) == 1

    def test_different_domains_separate(self):
        sources = [
            {"source_id": "src:thehindu.com"},
            {"source_id": "src:bbc.co.uk"},
        ]
        clusters = _cluster_sources(sources)
        assert len(clusters) == 2

    def test_high_style_overlap_clusters(self):
        sources = [
            {"source_id": "src:a.com", "style_markers": ["formal", "political", "govt", "hindi"]},
            {"source_id": "src:b.com", "style_markers": ["formal", "political", "govt", "state"]},
        ]
        # overlap = 3/5 = 0.6 >= threshold 0.5
        clusters = _cluster_sources(sources)
        assert len(clusters) == 1

    def test_low_style_overlap_stays_separate(self):
        sources = [
            {"source_id": "src:a.com", "style_markers": ["tabloid", "celebrity"]},
            {"source_id": "src:b.com", "style_markers": ["formal", "political", "govt"]},
        ]
        # overlap = 0/4 = 0.0 < threshold
        clusters = _cluster_sources(sources)
        assert len(clusters) == 2

    def test_both_flagged_clusters_together(self):
        sources = [
            {"source_id": "src:x.com", "is_flagged": True},
            {"source_id": "src:y.com", "is_flagged": True},
        ]
        clusters = _cluster_sources(sources)
        assert len(clusters) == 1

    def test_one_flagged_stays_separate(self):
        sources = [
            {"source_id": "src:x.com", "is_flagged": True},
            {"source_id": "src:y.com", "is_flagged": False},
        ]
        clusters = _cluster_sources(sources)
        assert len(clusters) == 2

    def test_empty_sources(self):
        assert _cluster_sources([]) == {}


class TestRunHappyPath:
    @pytest.mark.asyncio
    async def test_empty_sources_returns_empty(self, subagent):
        result = await subagent.run({"sources": [], "trace_id": "sc-001"})
        assert result["result"]["clusters"] == {}

    @pytest.mark.asyncio
    async def test_no_source_id_returns_error(self, subagent):
        result = await subagent.run({
            "sources": [{"domain": "bad.com"}],
            "trace_id": "sc-002",
        })
        assert "error" in result["result"]

    @pytest.mark.asyncio
    async def test_detects_multi_source_cluster(self, subagent):
        result = await subagent.run({
            "sources": [
                {"source_id": "src:a.com"},
                {"source_id": "src:b.a.com"},   # same root domain
            ],
            "trace_id": "sc-003",
        })
        r = result["result"]
        assert r["multi_source_clusters"] >= 1
        assert r["cluster_count"] == 1

    @pytest.mark.asyncio
    async def test_singleton_count_correct(self, subagent):
        result = await subagent.run({
            "sources": [
                {"source_id": "src:aaa.com"},
                {"source_id": "src:bbb.com"},
                {"source_id": "src:ccc.com"},
            ],
            "trace_id": "sc-004",
        })
        assert result["result"]["singleton_count"] == 3

    @pytest.mark.asyncio
    async def test_cost_is_zero(self, subagent):
        result = await subagent.run({"sources": [], "trace_id": "sc-cost"})
        assert result["meta"]["cost_inr"] == 0.0


class TestPenaltyPropagation:
    @pytest.mark.asyncio
    async def test_propagate_penalty_flags_cluster(self, subagent):
        result = await subagent.run({
            "sources": [
                {"source_id": "src:a.com", "is_flagged": True},
                {"source_id": "src:b.a.com"},   # same domain cluster
            ],
            "propagate_penalty": True,
            "trace_id": "sc-prop",
        })
        r = result["result"]
        assert len(r["flagged_clusters"]) >= 1

    @pytest.mark.asyncio
    async def test_no_propagation_by_default(self, subagent):
        result = await subagent.run({
            "sources": [
                {"source_id": "src:a.com", "is_flagged": True},
                {"source_id": "src:b.a.com"},
            ],
            "trace_id": "sc-no-prop",
        })
        # propagate_penalty defaults to False
        assert result["result"]["flagged_clusters"] == []
