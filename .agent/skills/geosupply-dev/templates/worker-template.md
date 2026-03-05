# Worker Template — BaseWorker Implementation

## Usage
Copy and modify for each new worker. All workers follow this exact pattern.

## Template

```python
"""
[WorkerName] — [one-line description]
Part of: GeoSupply AI FA v1
Layer: 5 (Worker)
Phase: [build phase number]
"""

from abc import ABC
from datetime import datetime
from pydantic import BaseModel
from geosupply.core.base_worker import BaseWorker
from geosupply.core.decorators import tracer, cost_tracker, retry, timeout, breaker
from geosupply.schemas import WorkerError


class [WorkerName](BaseWorker):
    """
    [Detailed description of what this worker does]

    CAPABILITIES: [LIST_OF_CAPABILITIES]
    TIER: [0|1|2|3]
    STATIC: [True if Tier-1 schema-strict, else False]
    SOURCES: [External APIs or data sources used]
    OUTPUT SCHEMA: [Pydantic schema name]
    """

    name = "[WorkerName]"
    tier = [0|1|2|3]
    use_static = [True|False]
    capabilities = {"[CAPABILITY_1]", "[CAPABILITY_2]"}
    max_retries = 3
    timeout_seconds = 60

    async def setup(self):
        """Load models, open connections. Called once."""
        # Example: self.model = await load_model("model_name")
        pass

    @tracer
    @cost_tracker
    @retry(max=3)
    @timeout(seconds=60)
    @breaker  # Use for external API calls ONLY
    async def process(self, input_data: dict) -> dict:
        """
        Core work function.

        Args:
            input_data: dict with task-specific fields

        Returns:
            dict with 'result' and 'meta' keys
            On failure: WorkerError schema
        """
        try:
            # === YOUR LOGIC HERE ===
            result = {}

            return {
                "result": result,
                "meta": {
                    "worker": self.name,
                    "tier": self.tier,
                    "cost_inr": 0.0,  # ALWAYS track cost
                    "timestamp": datetime.utcnow().isoformat(),
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
                timestamp=datetime.utcnow(),
            ).model_dump()

    async def teardown(self):
        """Cleanup. Called on shutdown."""
        pass
```

## STATIC Decoder Workers (Tier-1)
If `use_static = True`, the output MUST conform to a specific Pydantic schema.
The STATIC decoder constrains LLM output at decode time — no post-processing needed.

```python
# For STATIC workers, process() returns the exact Pydantic model:
return {
    "result": SentimentOutput(
        polarity=0.85,
        subjectivity=0.42,
        confidence=0.91
    ).model_dump(),
    "meta": { ... }
}
```
