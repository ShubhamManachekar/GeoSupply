# Testing Patterns — FA v2 (Updated Phase 14)

## Core Philosophy: "Not Mock, Logically"

Test REAL components — only mock external dependencies you can't control.

## Real Component Testing (PREFERRED)

```python
# tests/unit/test_logging_agent.py
import pytest
import tempfile
from pathlib import Path
from geosupply.agents.logging_agent import LoggingAgent, Severity

@pytest.fixture
async def agent():
    """REAL agent with temp SQLite DB — no mocks."""
    db = Path(tempfile.mktemp(suffix=".db"))
    a = LoggingAgent(db_path=db)
    await a.setup()
    yield a
    await a.teardown()
    if db.exists():
        db.unlink()

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_log_event(self, agent):
        ok = await agent.log(event_type="TEST", source="s", trace_id="t1")
        assert ok is True
        assert agent._total_logged == 1

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_sqlite_error_returns_false(self, agent):
        """Inject REAL error: drop table → INSERT fails."""
        agent._conn.execute("DROP TABLE swarm_logs")
        agent._conn.commit()
        result = await agent.log(event_type="FAIL", source="s", trace_id="t")
        assert result is False  # Real SQLite error caught

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_query_when_not_connected(self):
        a = LoggingAgent()
        a._conn = None
        rows = await a.query()
        assert rows == []
```

## Env-Patched Key Testing

```python
# tests/unit/test_security_agent.py
import os
from unittest.mock import patch
from geosupply.agents.security_agent import SecurityAgent, KeyNotFoundError

def test_get_key_success():
    sa = SecurityAgent()
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test"}):
        assert sa.get_key("groq") == "gsk_test"

def test_get_key_missing():
    sa = SecurityAgent()
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(KeyNotFoundError):
            sa.get_key("groq")
```

## Backdated Timestamp Testing (for rotation/expiry)

```python
# tests/unit/test_security_agent.py — key rotation
from datetime import datetime, timedelta, timezone

def test_rotate_aged_keys(agent):
    """Backdate issued_at to force rotation — NOT mocking time."""
    agent.generate_signing_key("OldAgent")
    old_key = agent.get_signing_key("OldAgent")
    agent._key_issued_at["OldAgent"] = datetime.now(timezone.utc) - timedelta(days=31)
    rotated = agent.rotate_event_keys()
    assert "OldAgent" in rotated
    assert agent.get_signing_key("OldAgent") != old_key
```

## Circuit Breaker State Machine Testing

```python
# tests/unit/test_decorators.py — HALF_OPEN probe
from geosupply.core.decorators import _CircuitBreakerState

def test_half_open_transition():
    cb = _CircuitBreakerState(max_failures=2, open_seconds=0)
    cb.record_failure()
    cb.record_failure()    # → OPEN
    assert cb.state == "OPEN"
    time.sleep(0.01)       # open_seconds=0 → instant
    assert cb.can_execute() is True  # → HALF_OPEN
    assert cb.state == "HALF_OPEN"
    cb.record_success()    # → CLOSED
    assert cb.state == "CLOSED"
```

## EventBus Signed Event Testing

```python
# tests/unit/test_event_bus.py
from datetime import datetime, timezone
from geosupply.core.event_bus import EventBus
from geosupply.schemas import Event

def _make_signed_event(bus, source, key, topic="test"):
    ts = datetime.now(timezone.utc)
    payload = {"data": "hello"}
    sig = EventBus.compute_signature(topic, source, payload, ts, key)
    return Event(topic=topic, source=source, payload=payload, timestamp=ts, signature=sig)

async def test_handler_error_doesnt_break_publish(bus):
    """Bad handler throws → good handler still runs → publish True."""
    async def bad(e): raise RuntimeError("boom")
    async def good(e): results.append(e)
    bus.subscribe("test", bad)
    bus.subscribe("test", good)
    event = _make_signed_event(bus, "AgentA", "key-a")
    assert await bus.publish(event) is True
    assert len(results) == 1
```

## Fixture Factory Pattern (G10) — for INTEGRATION tests only

```python
# tests/fixtures/mock_worker.py — use only when testing supervisors/orchestrator
from unittest.mock import AsyncMock
from geosupply.core.base_worker import BaseWorker

def create_mock_worker(name="TestWorker", tier=0, result=None):
    mock = AsyncMock(spec=BaseWorker)
    mock.name = name
    mock.tier = tier
    mock.process.return_value = result or {
        "result": {"test": True},
        "meta": {"worker": name, "tier": tier, "cost_inr": 0.0}
    }
    return mock
```

## Coverage Commands

```powershell
# Full coverage with deprecation warnings as errors
$env:PYTHONPATH="src"; python -m pytest tests/unit/ --cov=src/geosupply --cov-report=term-missing -W error::DeprecationWarning

# Quick test run
$env:PYTHONPATH="src"; python -m pytest tests/unit/ -v --tb=short -W error::DeprecationWarning

# Single file
$env:PYTHONPATH="src"; python -m pytest tests/unit/test_logging_agent.py -v
```

## Current Stats (Phase 14 Complete)
- 325 tests, 0 warnings, 97% coverage
- All agents at 95%+, 6 files at 100%
- 86/86 cross-phase audit checks passed
- 5/5 dynamic audit CLI checks passed
