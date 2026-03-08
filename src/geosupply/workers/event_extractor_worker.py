"""
EventExtractorWorker — Extracts geopolitical events from news texts into GeoEventRecord
Part of: GeoSupply AI FA v2
Layer: 5 (Worker)
Phase: 2
"""

from abc import ABC
from datetime import datetime, timezone
from geosupply.core.base_worker import BaseWorker
from geosupply.core.decorators import tracer, cost_tracker, retry, timeout, breaker
from geosupply.schemas import WorkerError, GeoEventRecord


class EventExtractorWorker(BaseWorker):
    """
    Extracts structured geopolitical events from raw text clippings.

    CAPABILITIES: EVENT_EXTRACT, NEWS_TAGGING
    TIER: 2 (qwen2.5:14b or similar for extraction tasks)
    STATIC: False
    SOURCES: Groq API / Ollama
    OUTPUT SCHEMA: GeoEventRecord
    """

    name = "EventExtractorWorker"
    tier = 2
    use_static = False
    capabilities = {"EVENT_EXTRACT", "NEWS_TAGGING"}
    max_retries = 3
    timeout_seconds = 60

    async def setup(self):
        """Load models, open connections. Called once."""
        pass

    @tracer
    @cost_tracker
    @retry(max_retries=3)
    @timeout(seconds=60)
    @breaker
    async def process(self, input_data: dict) -> dict:
        """
        Core work function to extract events.

        Args:
            input_data: dict containing 'text' (the news clipping) and 'source'

        Returns:
            dict with 'result' (GeoEventRecord data) and 'meta'
        """
        try:
            clipping_text = input_data.get("text")
            source = input_data.get("source", "UNKNOWN")
            
            if not clipping_text:
                raise ValueError("Missing 'text' in input_data")

            # === SIMULATED LLM EXTRACTION LOGIC ===
            # In a real environment, this calls the LLM via api_client (e.g., Groq)
            # using Tier-2 model passing the clipping_text and returning JSON matching GeoEventRecord.
            
            # Since we are implementing the template logic without direct LLM API access here,
            # we provide a stubbed structure representing a successful parse based on input.
            
            # Simulated parsing of the clipping_text:
            event_type = "OTHER"
            if "war" in clipping_text.lower() or "conflict" in clipping_text.lower():
                event_type = "WAR"
            elif "cyclone" in clipping_text.lower() or "earthquake" in clipping_text.lower():
                event_type = "CALAMITY"
                
            locations = []
            if "india" in clipping_text.lower(): locations.append("India")
            if "china" in clipping_text.lower(): locations.append("China")

            record = GeoEventRecord(
                event_type=event_type,
                description=clipping_text[:200] + "..." if len(clipping_text) > 200 else clipping_text,
                source_clipping=source,
                severity=0.85, # Simulated severity score
                locations=locations,
                date_occurred=datetime.now(timezone.utc)
            )

            return {
                "result": record.model_dump(),
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.05,  # Simulated cost representing a Tier 2 API call
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            }
        except Exception as e:
            return WorkerError(
                error_type="INTERNAL",
                message=str(e),
                worker_name=self.name,
                retry_count=self.max_retries,
                cost_inr=0.0,
                trace_id=input_data.get("trace_id", "unknown"),
                timestamp=datetime.now(timezone.utc),
            ).model_dump()

    async def teardown(self):
        """Cleanup. Called on shutdown."""
        pass
