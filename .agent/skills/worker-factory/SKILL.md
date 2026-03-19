---
name: worker-factory
description: Rapid worker scaffolding for GeoSupply Layer 5. Complete patterns for all 4 worker archetypes — Tier-1 STATIC, Tier-2 translation, Tier-3 RAG, and CPU-only ML. Includes test scaffold and audit registration.
---

# Worker Factory — Layer 5 Rapid Scaffolding

> Custom GeoSupply skill — build production-ready workers in under 5 minutes

## Worker Archetypes

| Archetype | Tier | Use When | Example |
|-----------|------|----------|---------|
| STATIC decoder | SMALL_3B | Schema-strict extraction | SentimentWorker, NERWorker, SourceCredWorker, CyberThreatWorker, SupplierWorker, SanctionsWorker |
| Translation/Analysis | MEDIUM_14B | Multi-language, network analysis | TranslationWorker, NetworkWorker, CIBWorker, PropagandaWorker |
| Verification/RAG | LARGE_20B | Claim verification, brief synthesis | VerifierWorker |
| CPU-only | CPU_ONLY | ML models, rule-based processing | ConflictWorker, StressWorker |

## Implemented Intel Workers (Phase 4 — as of 2026-03-19)
| Worker | Tier | Schema | Status |
|--------|------|--------|--------|
| SourceCredWorker | 1 STATIC | SourceCredOutput | ✅ |
| CyberThreatWorker | 1 STATIC | CyberThreatScore | ✅ |
| SupplierWorker | 1 STATIC | SupplierScore | ✅ |
| SanctionsWorker | 1 STATIC | SanctionsOutput | ✅ |
| NetworkWorker | 2 | dict | ✅ |
| CIBWorker | 2 | dict | ✅ |
| VerifierWorker | 3 | - | ⬜ |
| AuthorWorker | 3 | - | ⬜ |

---

## 1. STATIC Decoder Worker (Tier-1)

```python
# Template: Copy → rename class → update name/capabilities → implement _process_text()

from __future__ import annotations
from datetime import datetime, timezone
from geosupply.core.base_worker import BaseWorker
from geosupply.core.decorators import tracer, cost_tracker
from geosupply.schemas import WorkerError
from geosupply.config import LLMTier


class {Name}Worker(BaseWorker):
    """
    {One line description}.
    Tier-1 STATIC decoder — schema-strict, zero hallucination risk.
    Cost: ~₹0.001 per call (local llama3.2:3b, no API).
    """
    name = "{name}"
    tier = LLMTier.SMALL_3B
    use_static = True   # MANDATORY for Tier-1 schema-strict workers
    capabilities = ["{capability_1}", "{capability_2}"]

    async def setup(self) -> None:
        await super().setup()
        # Initialize any resources (model loading, DB connections)

    async def teardown(self) -> None:
        await super().teardown()
        # Clean up resources

    @tracer
    @cost_tracker
    async def process(self, input_data: dict) -> dict:
        """
        Input: {"text": str, "language": str, "trace_id": str}
        Output: {Schema}.model_dump() + meta
        """
        try:
            text = input_data.get("text", "")
            if not text:
                return self._error("VALIDATION", "Empty text input", input_data)

            result = await self._process_text(text)

            return {
                "result": result,
                "meta": {
                    "cost_inr": 0.001,   # Tier-1 local model cost
                    "tier": self.tier.value,
                    "trace_id": input_data.get("trace_id", ""),
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        except Exception as exc:
            return self._error("INTERNAL", str(exc), input_data)

    async def _process_text(self, text: str) -> dict:
        """Core processing logic — override this."""
        raise NotImplementedError

    def _error(self, error_type: str, message: str, input_data: dict) -> dict:
        return WorkerError(
            error_type=error_type,
            message=message,
            worker_name=self.name,
            trace_id=input_data.get("trace_id", ""),
            cost_inr=0.0,
            occurred_at=datetime.now(timezone.utc),
        ).model_dump()
```

---

## 2. CPU-Only Worker (ML / Rule-Based)

```python
class {Name}Worker(BaseWorker):
    """
    {One line description}.
    CPU-only — no LLM, pure computation or ML model.
    Cost: ₹0.000 (zero API cost).
    """
    name = "{name}"
    tier = LLMTier.CPU_ONLY
    capabilities = ["{capability}"]

    async def setup(self) -> None:
        await super().setup()
        # Load model: self._model = joblib.load("models/{name}.pkl")

    @tracer
    @cost_tracker
    async def process(self, input_data: dict) -> dict:
        try:
            features = self._extract_features(input_data)
            result = self._model.predict([features])[0]
            return {
                "result": {"prediction": float(result), "region": input_data.get("region")},
                "meta": {
                    "cost_inr": 0.0,
                    "tier": "CPU_ONLY",
                    "model_version": self._model_version,
                    "trace_id": input_data.get("trace_id", ""),
                }
            }
        except Exception as exc:
            return self._error("INTERNAL", str(exc), input_data)
```

---

## 3. External API Worker (with @breaker)

```python
from geosupply.core.decorators import breaker

class {Name}Worker(BaseWorker):
    """
    {One line description}.
    Fetches data from external API.
    """
    name = "{name}"
    tier = LLMTier.CPU_ONLY   # No LLM — API ingestion only
    capabilities = ["{capability}"]

    async def setup(self) -> None:
        await super().setup()
        self._api_key = self.security_agent.get_key("{api_key_name}")
        self._http = httpx.AsyncClient(timeout=30.0)

    async def teardown(self) -> None:
        await self._http.aclose()
        await super().teardown()

    @tracer
    @cost_tracker
    @breaker   # REQUIRED for all external API calls
    async def process(self, input_data: dict) -> dict:
        try:
            response = await self._http.get(
                "{api_endpoint}",
                headers={"Authorization": f"Bearer {self._api_key}"},
                params=input_data.get("params", {}),
            )
            response.raise_for_status()
            return {
                "result": response.json(),
                "meta": {"cost_inr": 0.0, "trace_id": input_data.get("trace_id", "")}
            }
        except httpx.HTTPError as exc:
            return self._error("EXTERNAL_API", str(exc), input_data)
        except Exception as exc:
            return self._error("INTERNAL", str(exc), input_data)
```

---

## 4. Test Scaffold

```python
# File: tests/unit/test_{name}_worker.py

import pytest
from datetime import datetime, timezone
from geosupply.workers.{name}_worker import {Name}Worker


@pytest.fixture
async def worker():
    """Real worker — not a mock. Use ZERO_MOCK policy."""
    w = {Name}Worker()
    await w.setup()
    yield w
    await w.teardown()


class TestHappyPath:
    async def test_process_valid_input(self, worker):
        result = await worker.process({"text": "Valid test input", "trace_id": "test-001"})
        assert "result" in result
        assert "meta" in result
        assert "cost_inr" in result["meta"]
        assert isinstance(result["meta"]["cost_inr"], float)

    async def test_cost_tracked_in_inr(self, worker):
        result = await worker.process({"text": "Test", "trace_id": "test-002"})
        assert result["meta"]["cost_inr"] >= 0.0  # Never negative


class TestErrorPaths:
    async def test_empty_input_returns_worker_error(self, worker):
        result = await worker.process({"text": "", "trace_id": "test-003"})
        assert result.get("error_type") == "VALIDATION"

    async def test_missing_text_key_returns_worker_error(self, worker):
        result = await worker.process({"trace_id": "test-004"})
        assert "error_type" in result   # WorkerError schema

    async def test_exception_returns_structured_error(self, worker, monkeypatch):
        async def bad_process(text):
            raise RuntimeError("Simulated failure")
        monkeypatch.setattr(worker, "_process_text", bad_process)
        result = await worker.process({"text": "Test", "trace_id": "test-005"})
        assert result.get("error_type") == "INTERNAL"
        assert result.get("worker_name") == worker.name


class TestEdgeCases:
    async def test_very_long_text(self, worker):
        long_text = "word " * 2000
        result = await worker.process({"text": long_text, "trace_id": "test-006"})
        assert "result" in result or "error_type" in result  # Either is acceptable

    async def test_unicode_text(self, worker):
        result = await worker.process({"text": "नमस्ते दुनिया", "trace_id": "test-007"})
        assert "result" in result or "error_type" in result
```

---

## 5. Audit Registration (Automatic)

Workers are auto-discovered by the audit system through Python's `__subclasses__()`. No manual registration needed — just ensure:

```python
# 1. Class inherits BaseWorker (direct or indirect)
class MyWorker(BaseWorker): ...

# 2. Module is importable from geosupply.workers package
# File: src/geosupply/workers/my_worker.py
# Import: from geosupply.workers.my_worker import MyWorker

# 3. Audit verification:
# python -m geosupply.cli.audit --level strict
# → Should show MyWorker in discovered workers list
```

---

## 6. Worker Creation Checklist

- [ ] Class inherits `BaseWorker`
- [ ] `name`, `tier`, `capabilities` defined as class attributes
- [ ] `use_static = True` if Tier-1 schema-strict
- [ ] `setup()` and `teardown()` implemented
- [ ] `@tracer` and `@cost_tracker` applied to `process()`
- [ ] `@breaker` applied if any external API call
- [ ] Empty/invalid input returns `WorkerError` schema (never raises)
- [ ] `meta.cost_inr` present in every successful return
- [ ] `datetime.now(timezone.utc)` — never `datetime.utcnow()`
- [ ] `SecurityAgent.get_key()` for all API keys
- [ ] Test file created: `tests/unit/test_{name}_worker.py`
- [ ] Test covers: happy path, empty input, exception injection, unicode
- [ ] Coverage ≥ 85% on the new file
- [ ] `python -m geosupply.cli.audit --level strict` passes

---

## Related Skills
- `agent-designer` — For Layer 3 agents (not workers)
- `supervisor-designer` — Supervisors that manage workers
- `phase-gate-auditor` — Gate check after adding new worker
- `geosupply-dev` — Core conventions every worker must follow
