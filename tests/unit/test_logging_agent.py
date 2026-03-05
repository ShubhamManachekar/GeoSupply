"""Unit tests for LoggingAgent — SQLite logging, EventBus subscription, queries."""

import pytest
import tempfile
from pathlib import Path
from geosupply.agents.logging_agent import LoggingAgent, Severity
from geosupply.schemas import Event


@pytest.fixture
async def agent():
    db = Path(tempfile.mktemp(suffix=".db"))
    a = LoggingAgent(db_path=db)
    await a.setup()
    yield a
    await a.teardown()
    if db.exists():
        db.unlink()


class TestLogging:
    @pytest.mark.asyncio
    async def test_log_basic_event(self, agent):
        success = await agent.log(
            event_type="TEST_EVENT",
            source="UnitTest",
            message="hello world",
            trace_id="t1",
            severity=Severity.INFO,
        )
        assert success is True
        assert agent._total_logged == 1

    @pytest.mark.asyncio
    async def test_log_with_cost(self, agent):
        await agent.log(
            event_type="COST_EVENT",
            source="Worker",
            cost_inr=0.05,
            trace_id="t2",
        )
        assert agent._total_cost_inr == 0.05

    @pytest.mark.asyncio
    async def test_severity_filter(self, agent):
        agent._min_severity = Severity.WARN
        logged = await agent.log(
            event_type="DEBUG_EVENT",
            source="test",
            severity=Severity.DEBUG,
            trace_id="t3",
        )
        assert logged is False  # Should be filtered

    @pytest.mark.asyncio
    async def test_severity_passes_above_min(self, agent):
        agent._min_severity = Severity.WARN
        logged = await agent.log(
            event_type="ERROR_EVENT",
            source="test",
            severity=Severity.ERROR,
            trace_id="t4",
        )
        assert logged is True


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_all(self, agent):
        await agent.log(event_type="A", source="s1", trace_id="t1")
        await agent.log(event_type="B", source="s2", trace_id="t2")
        rows = await agent.query()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_query_by_source(self, agent):
        await agent.log(event_type="A", source="worker1", trace_id="t1")
        await agent.log(event_type="B", source="worker2", trace_id="t2")
        rows = await agent.query(source="worker1")
        assert len(rows) == 1
        assert rows[0]["source"] == "worker1"

    @pytest.mark.asyncio
    async def test_query_by_trace_id(self, agent):
        await agent.log(event_type="A", source="s", trace_id="trace-abc")
        await agent.log(event_type="B", source="s", trace_id="trace-def")
        rows = await agent.query(trace_id="trace-abc")
        assert len(rows) == 1


class TestEventBusIntegration:
    @pytest.mark.asyncio
    async def test_handle_event(self, agent):
        event = Event(
            topic="test_topic", source="AgentX",
            payload={"trace_id": "ev-001", "data": "hello"},
        )
        await agent.handle_event(event)
        assert agent._total_logged == 1
        rows = await agent.query()
        assert rows[0]["event_type"] == "test_topic"


class TestExecuteContract:
    @pytest.mark.asyncio
    async def test_execute_log_action(self, agent):
        result = await agent.execute({
            "action": "log",
            "event_type": "TASK_EVENT",
            "source": "Supervisor",
            "trace_id": "t1",
        })
        assert result["result"]["logged"] is True
        assert result["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_execute_query_action(self, agent):
        await agent.log(event_type="A", source="s", trace_id="t1")
        result = await agent.execute({"action": "query"})
        assert result["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, agent):
        result = await agent.execute({"action": "unknown"})
        assert "error" in result["result"]


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_query_when_conn_is_none(self):
        """L180: query() returns [] when DB not connected."""
        a = LoggingAgent()
        a._conn = None
        rows = await a.query()
        assert rows == []

    @pytest.mark.asyncio
    async def test_query_by_severity(self, agent):
        """L189-190: query filters by severity string."""
        await agent.log(event_type="A", source="s", trace_id="t1", severity=Severity.ERROR)
        await agent.log(event_type="B", source="s", trace_id="t2", severity=Severity.INFO)
        rows = await agent.query(severity="ERROR")
        assert len(rows) == 1
        assert rows[0]["severity"] == "ERROR"

    @pytest.mark.asyncio
    async def test_auto_setup_on_log(self):
        """L132: log() auto-initializes DB when _conn is None."""
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        a = LoggingAgent(db_path=db)
        assert a._conn is None
        ok = await a.log(event_type="TEST", source="test", trace_id="auto")
        assert ok is True
        assert a._conn is not None
        await a.teardown()
        if db.exists():
            db.unlink()

    @pytest.mark.asyncio
    async def test_stats_property(self, agent):
        """L242: stats returns aggregate counters."""
        await agent.log(event_type="A", source="s", trace_id="t1", cost_inr=0.03)
        s = agent.stats
        assert s["total_logged"] == 1
        assert s["total_cost_inr"] == 0.03
        assert "db_path" in s

    @pytest.mark.asyncio
    async def test_sqlite_error_returns_false(self, agent):
        """L153-155: Real SQLite error → returns False."""
        # Close connection to force OperationalError on write
        agent._conn.close()
        agent._conn = None
        # Create a new agent with invalid path to force DB error
        import tempfile, os
        bad_path = Path(tempfile.mktemp(suffix=".db"))
        bad = LoggingAgent(db_path=bad_path)
        await bad.setup()
        # Drop the table to force an INSERT error
        bad._conn.execute("DROP TABLE swarm_logs")
        bad._conn.commit()
        result = await bad.log(event_type="FAIL", source="s", trace_id="t")
        assert result is False  # SQLite error caught
        await bad.teardown()
        if bad_path.exists():
            bad_path.unlink()

    @pytest.mark.asyncio
    async def test_query_combined_filters(self, agent):
        """Multiple filters work together logically."""
        await agent.log(event_type="A", source="w1", trace_id="tr1", severity=Severity.ERROR)
        await agent.log(event_type="B", source="w1", trace_id="tr2", severity=Severity.INFO)
        await agent.log(event_type="C", source="w2", trace_id="tr1", severity=Severity.ERROR)
        rows = await agent.query(source="w1", severity="ERROR")
        assert len(rows) == 1
        assert rows[0]["trace_id"] == "tr1"
