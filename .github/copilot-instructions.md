# GeoSupply AI — Copilot Instructions
# These rules are enforced across ALL code in this repository.

## Architecture Rules
- Every agent class inherits from BaseWorker/BaseSubAgent/BaseAgent/BaseSupervisor
- All inter-agent communication uses AgentMessage Pydantic model (schema #1)
- All costs tracked in INR, never USD
- HALLUCINATION_FLOOR = 0.70 (never lower this)
- Tier-1 workers MUST use STATIC decoder (use_static=True)
- No lateral worker-to-worker or supervisor-to-supervisor communication
- All events published through EventBus must be signed (HMAC-SHA256)
- Every failed worker returns WorkerError schema (#23), never raw exceptions
- Agent state transitions use _transition() with guard validation (G2)

## Code Style
- Python 3.10+, type hints everywhere
- Pydantic v2 for all schemas (every schema has schema_version field)
- async/await for all I/O
- @breaker decorator for external API calls
- @internal_breaker for Tier-3+ agent calls
- SecurityAgent.get_key() for all API keys — never hardcode
- Use structlog for logging

## Testing
- pytest with 80% coverage minimum
- All workers must have mock fixtures (tests/fixtures/mock_worker.py)
- Integration tests use synthetic data only (tests/fixtures/synthetic_data.py)
- Use @pytest.mark.asyncio for async test functions
- Use InMemoryEventBus from tests/fixtures/mock_eventbus.py for event testing

## Schema Rules
- Every schema inherits from pydantic.BaseModel
- Every schema has schema_version: int = 1
- Field validators: use Field(ge=, le=) for scores (0.0-1.0)
- Use Literal types for constrained string fields
- KnowledgeUpdateRequest uses dedup_key property for batching

## Import Conventions
```python
from geosupply.config import HALLUCINATION_FLOOR, BUDGET_CAP_INR
from geosupply.schemas import AgentMessage, WorkerError
from geosupply.core import BaseWorker, BaseAgent, EventBus
from geosupply.core.decorators import tracer, cost_tracker, breaker
```
