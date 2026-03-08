import pytest
from datetime import datetime, timezone
from geosupply.workers.event_extractor_worker import EventExtractorWorker
from geosupply.schemas import GeoEventRecord

@pytest.fixture
async def worker():
    """REAL worker — no mocks for the class itself."""
    w = EventExtractorWorker()
    await w.setup()
    yield w
    await w.teardown()

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_extract_war_event(self, worker):
        input_data = {
            "text": "A massive war broke out yesterday across the northern border of India and China.",
            "source": "GlobalNews",
            "trace_id": "test-trace-1"
        }
        res = await worker.process(input_data)
        
        # Validate structure
        assert "result" in res
        assert "meta" in res
        
        # Validate metadata
        assert res["meta"]["worker"] == "EventExtractorWorker"
        assert res["meta"]["cost_inr"] == 0.05
        assert res["meta"]["tier"] == 2
        
        # Validate parsed result matches GeoEventRecord schema
        record = GeoEventRecord(**res["result"])
        assert record.event_type == "WAR"
        assert record.source_clipping == "GlobalNews"
        assert "India" in record.locations
        assert "China" in record.locations
        assert "war broke out" in record.description

    @pytest.mark.asyncio
    async def test_extract_calamity_event(self, worker):
        input_data = {
            "text": "A terrible cyclone is approaching the eastern coast.",
            "source": "WeatherReport"
        }
        res = await worker.process(input_data)
        
        record = GeoEventRecord(**res["result"])
        assert record.event_type == "CALAMITY"

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_missing_text_returns_worker_error(self, worker):
        """Inject REAL error: missing required input_data field."""
        input_data = {"source": "GlobalNews", "trace_id": "err-trace"}
        res = await worker.process(input_data)
        
        # Should return WorkerError (dict dumped)
        assert "error_type" in res
        assert res["error_type"] == "INTERNAL"
        assert "Missing 'text'" in res["message"]
        assert res["worker_name"] == "EventExtractorWorker"
        assert res["trace_id"] == "err-trace"
