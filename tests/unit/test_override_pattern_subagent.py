"""Tests for OverridePatternSubAgent."""

import pytest
from datetime import datetime, timedelta, timezone

from geosupply.subagents.override_pattern_subagent import OverridePatternSubAgent
from geosupply.schemas import LoopholeFinding, OverrideRecord


def _make_override(
    action: str = "halt",
    target: str = "NewsWorker",
    days_ago: float = 1.0,
) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return OverrideRecord(
        admin_id="admin01",
        action=action,
        target=target,
        reason="test",
        timestamp=ts,
        totp_verified=True,
    ).model_dump()


@pytest.fixture
def agent():
    return OverridePatternSubAgent()


class TestOverridePatternSubAgentClean:
    @pytest.mark.asyncio
    async def test_no_patterns_clean_data(self, agent):
        overrides = [
            _make_override("halt", "NewsWorker", 10.0),
            _make_override("release", "AISWorker", 12.0),
            _make_override("rollback", "SentimentWorker", 15.0),
        ]
        result = await agent.run({"overrides": overrides})
        assert result["result"]["patterns_detected"] == 0

    @pytest.mark.asyncio
    async def test_empty_input(self, agent):
        result = await agent.run({"overrides": []})
        assert result["result"]["patterns_detected"] == 0
        assert result["result"]["override_count"] == 0
        assert result["meta"]["cost_inr"] == 0.0


class TestOverridePatternSubAgentWeeklyLimit:
    @pytest.mark.asyncio
    async def test_weekly_limit_breach(self, agent):
        # 6 overrides within last 2 days — exceeds limit of 5
        overrides = [_make_override("halt", f"Worker{i}", 0.5) for i in range(6)]
        result = await agent.run({"overrides": overrides})
        check_ids = [f["check_id"] for f in result["result"]["findings"]]
        assert "OVR-001" in check_ids


class TestOverridePatternSubAgentFavouritism:
    @pytest.mark.asyncio
    async def test_source_favouritism(self, agent):
        # 4 overrides all targeting "NewsWorker" — exceeds limit of 3
        overrides = [_make_override("halt", "NewsWorker", i * 10.0) for i in range(1, 5)]
        result = await agent.run({"overrides": overrides})
        check_ids = [f["check_id"] for f in result["result"]["findings"]]
        assert "OVR-002" in check_ids


class TestOverridePatternSubAgentTimeCluster:
    @pytest.mark.asyncio
    async def test_time_cluster(self, agent):
        # 4 overrides within 30 minutes — exceeds limit of 3
        base = datetime.now(timezone.utc) - timedelta(hours=2)
        overrides = []
        for i in range(4):
            ts = base + timedelta(minutes=i * 5)
            overrides.append({
                "admin_id": "admin01",
                "action": "halt",
                "target": f"Worker{i}",
                "reason": "test",
                "timestamp": ts.isoformat(),
                "totp_verified": True,
                "schema_version": 1,
            })
        result = await agent.run({"overrides": overrides})
        check_ids = [f["check_id"] for f in result["result"]["findings"]]
        assert "OVR-003" in check_ids


class TestOverridePatternSubAgentBypass:
    @pytest.mark.asyncio
    async def test_factcheck_bypass_limit(self, agent):
        # 10 overrides, 3 with action="approve" → 30% > 20%
        overrides = (
            [_make_override("approve", f"Worker{i}", i * 5.0) for i in range(3)]
            + [_make_override("halt", f"Other{i}", i * 5.0 + 1.0) for i in range(7)]
        )
        result = await agent.run({"overrides": overrides})
        check_ids = [f["check_id"] for f in result["result"]["findings"]]
        assert "OVR-004" in check_ids


class TestOverridePatternSubAgentFindingsValid:
    @pytest.mark.asyncio
    async def test_all_findings_are_loophole_finding_parseable(self, agent):
        overrides = [_make_override("halt", "NewsWorker", 0.5) for _ in range(6)]
        result = await agent.run({"overrides": overrides})
        for finding in result["result"]["findings"]:
            validated = LoopholeFinding.model_validate(finding)
            assert validated.check_id
