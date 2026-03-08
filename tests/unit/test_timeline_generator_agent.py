import pytest
from datetime import datetime, timezone, timedelta
from geosupply.agents.timeline_generator_agent import TimelineGeneratorAgent, InvalidStateTransition
from geosupply.schemas import GeoEventRecord, GeoEventTimeline

@pytest.fixture
async def agent():
    """REAL agent — no mocks."""
    a = TimelineGeneratorAgent()
    yield a

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_timeline_generation(self, agent):
        ts1 = datetime.now(timezone.utc) - timedelta(days=2)
        ts2 = datetime.now(timezone.utc) - timedelta(days=1)
        ts3 = datetime.now(timezone.utc)
        
        e1 = GeoEventRecord(
            event_type="POLITICAL_SHIFT",
            description="Election results announced",
            source_clipping="NewsA",
            severity=0.5,
            locations=["India"],
            date_occurred=ts1
        ).model_dump()
        
        e2 = GeoEventRecord(
            event_type="TRADE_DISPUTE",
            description="Tariffs raised",
            source_clipping="NewsB",
            severity=0.7,
            locations=["India", "USA"],
            date_occurred=ts2
        ).model_dump()
        
        e3 = GeoEventRecord(
            event_type="WAR",
            description="Border skirmish",
            source_clipping="NewsC",
            severity=0.9,
            locations=["India"],
            date_occurred=ts3
        ) # Pass as Pydantic object to test mixed input handling

        task = {
            "timeline_name": "Test_Timeline",
            "events": [e2, e1, e3] # Deliberately out of order
        }
        
        assert agent._state == "IDLE"
        res = await agent.execute(task)
        assert agent._state == "IDLE" # State should recover to IDLE
        
        assert "result" in res
        assert "meta" in res
        
        # Verification
        timeline = GeoEventTimeline(**res["result"])
        assert timeline.timeline_name == "Test_Timeline"
        assert len(timeline.nodes) == 3
        
        # Chronological ordering check
        assert timeline.nodes[0].event.event_type == "POLITICAL_SHIFT"
        assert timeline.nodes[1].event.event_type == "TRADE_DISPUTE"
        assert timeline.nodes[2].event.event_type == "WAR"
        
        # Link check
        assert "Event-1" in timeline.nodes[0].related_events
        assert "Event-0" in timeline.nodes[1].related_events
        assert "Event-2" in timeline.nodes[1].related_events
        assert "Event-1" in timeline.nodes[2].related_events
        
        assert "Escalation" in timeline.identified_trend

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_no_events_provided(self, agent):
        task = {"timeline_name": "Empty"}
        res = await agent.execute(task)
        
        assert "error" in res
        assert "No events provided" in res["error"]
        assert agent._state == "IDLE" # Successful recovery

class TestStateGuards:
    def test_invalid_state_transition(self, agent):
        import pytest
        assert agent._state == "IDLE"
        
        # IDLE -> DONE is not allowed (must go to BUSY first)
        with pytest.raises(InvalidStateTransition) as excinfo:
            agent._transition("DONE")
            
        assert "IDLE → DONE not allowed" in str(excinfo.value)
