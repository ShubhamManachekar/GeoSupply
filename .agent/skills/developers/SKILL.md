---
name: developers
description: FA v3 development rules, test policies, and audit procedures for any developer interacting with the GeoSupply AI codebase.
---

# GeoSupply Developers Skill (FA v3)

## Introduction
This skill represents the fundamental laws of developing within the GeoSupply FA v3 ecosystem. Whether you are a human developer, Copilot, or an autonomous AI agent like Antigravity, **THESE RULES ARE ABSOLUTE**.

## The ZERO MOCK Policy (Rule 16)
The geo-political data landscape is fragile. Our testing cannot be.
- **NO `unittest.mock.Mock` or `AsyncMock`** for any core component being tested.
- If you test `LoggingAgent`, use a real, temporary SQLite database (`Path(tempfile.mktemp(suffix=".db"))`).
- If you test the Circuit Breaker, simulate real failures (e.g., dropping a table to force an SQLite failure) and observe the `HALF_OPEN` state.
- **Exception**: You may mock external 3rd-party dependencies (like `aiohttp.ClientSession` network calls to APIs) or use `tests/fixtures/mock_worker.py` only when isolation is required by fixture contracts.

## Dynamic Discovery & Audit (Rules 17-24)
Phase gates cannot be closed without running a full dynamic audit.
1. **Never Hardcode Counts**: Do not hardcode lists of agents/schemas/workers. Use `pkgutil.walk_packages()` or `__subclasses__()` for discovery.
2. **Schema Synchronization**: Any schema added to `ALL_SCHEMAS` **MUST** have a corresponding entry in `SCHEMA_VERSIONS`.
3. **MRO Validation**: `process()` must be overridden in Workers; Agents must have a valid Method Resolution Order validating `BaseAgent`.
4. **Phase-End Test**: Run `$env:PYTHONPATH="src"; python -m geosupply.cli.audit --level strict` to validate Logic Breakage, Logic Gaps, and Connectivity before closing any development phase.

## Banned Practices
- `datetime.utcnow()`: **BANNED**. Python 3.14 deprecates this. Use `datetime.now(timezone.utc)` everywhere.
- Bare `except Exception: pass`: **BANNED**. Log the exception and return a structured `WorkerError` (Schema #23) with trace ID and cost context attached.
- Hardcoded API Keys: **BANNED**. Use `SecurityAgent.get_key("name")` to pull securely from the `.env` configuration.
- Returning USD costs: **BANNED**. Always track and report `cost_inr` inside the `meta` dict.

## Verification
If you modify code, always verify test coverage:
```bash
$env:PYTHONPATH="src"; python -m pytest tests/unit/ --cov=src/geosupply --cov-report=term-missing -W error::DeprecationWarning
```
*Coverage FLOOR is 80%. Target 95%+.*
