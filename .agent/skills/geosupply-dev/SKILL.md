---
name: geosupply-dev
description: GeoSupply AI development conventions, architecture rules, and code generation templates for FA v1
---

# GeoSupply AI Development Skill

## Architecture Context

GeoSupply AI is an India-centric geopolitical supply chain intelligence platform using a multi-agent swarm (FA v1, ~137 components). Read `f:\GeoSupply\Documents\DEVELOPMENT_TRAIL.md` for full context.

## Locked Rules (NEVER Override)

1. **DAG + Pydantic v2** — All inter-component communication uses typed `AgentMessage` schema
2. **3-tier LLM routing**: Tier 1 (3b + STATIC) → Tier 2 (14b) → Tier 3 (20b)
3. **No lateral communication** — Workers/Supervisors NEVER talk to peers directly
4. **Single-writer** for state (Tier 0 authority)
5. **Infrastructure OFF critical path**
6. **XGBoost ISOLATED from LLMs**
7. **HALLUCINATION_FLOOR = 0.70** (LOCKED)
8. **All costs in INR** — never USD
9. **TRUST NOTHING** — validate every data flow
10. **Every agent has a watchdog**

## Code Conventions

```python
# Python 3.10+, type hints everywhere
# Pydantic v2 for ALL schemas
# async/await for ALL I/O operations
# @breaker for external API calls
# @internal_breaker for Tier-3+ agent calls
# SecurityAgent.get_key() for ALL API keys — never hardcode
# Every process() must track cost_inr in meta
```

## Banned Patterns (Learned from Phase 0+1)

```python
# ❌ BANNED: Python 3.14 deprecated
datetime.utcnow()

# ✅ REQUIRED: timezone-aware
from datetime import datetime, timezone
datetime.now(timezone.utc)

# ❌ BANNED: bare exception swallowing
except Exception:
    pass

# ✅ REQUIRED: log + return structured error
except Exception as exc:
    logger.error("...: %s", exc)
    return WorkerError(error_type="INTERNAL", message=str(exc), ...)

# ❌ BANNED: hardcoded API keys
api_key = "sk-..."

# ✅ REQUIRED: SecurityAgent vault
key = security_agent.get_key("groq")
```

## Module Creation Checklist

When creating any new module:

1. [ ] Inherits correct base class (BaseWorker/BaseSubAgent/BaseAgent/BaseSupervisor)
2. [ ] Has `name`, `tier`, `capabilities` defined
3. [ ] Uses `async def process()` / `async def run()` / `async def execute()`
4. [ ] Returns structured `dict` with `result` and `meta` (including `cost_inr`)
5. [ ] On failure, returns `WorkerError` schema (schema #23)
6. [ ] Has `setup()` and `teardown()` lifecycle hooks
7. [ ] Has corresponding test in `tests/unit/`
8. [ ] Tests use REAL logic — no AsyncMock for the component under test
9. [ ] Type hints on all function signatures
10. [ ] Docstring with class purpose and data flow
11. [ ] All datetime calls use `datetime.now(timezone.utc)` — never `utcnow()`
12. [ ] Agent `execute()` handles unknown actions with error dict

## Testing Rules (Learned from Phase 1)

### Philosophy: "Not Mock, Logically"
- Test the **real component** — only mock external dependencies (APIs, DBs in other services)
- Use **temp files** for SQLite tests (`Path(tempfile.mktemp(suffix=".db"))`)
- Use **env patching** for API key tests (`patch.dict(os.environ, {...})`)
- Use **backdated timestamps** for rotation/expiry tests (not time mocking)
- Inject **real errors** (drop tables, corrupt state) — don't just mock exceptions

### Coverage Targets
- Every file **must** be ≥ 85% (project gate: 80%)
- Run with `-W error::DeprecationWarning` to catch deprecations as failures
- Coverage command: `$env:PYTHONPATH="src"; python -m pytest tests/unit/ --cov=src/geosupply --cov-report=term-missing -W error::DeprecationWarning`

### Test Structure Pattern
```python
@pytest.fixture
async def agent():
    """Fixture with real setup/teardown — not a mock."""
    a = MyAgent(db_path=Path(tempfile.mktemp(suffix=".db")))
    await a.setup()
    yield a
    await a.teardown()

class TestHappyPath:
    """Normal operations with real data."""

class TestErrorPaths:
    """Error injection — real DB errors, invalid input, budget exhaustion."""

class TestEdgeCases:
    """Boundary conditions — empty input, max limits, zero budget."""

class TestExecuteContract:
    """BaseAgent.execute() for each action."""
```

### Cross-Phase Audit Checklist
After completing any phase, run these checks:
1. [ ] **Connectivity**: All imports resolve, no circular deps
2. [ ] **Logic Gaps**: Every error path returns structured error, agents recover to IDLE
3. [ ] **Breakages**: Class hierarchies match architecture, schema counts match
4. [ ] **Oversights**: All claimed features actually exist in code
5. [ ] **Hallucinations**: DEVELOPMENT_TRAIL claims match actual implementation
6. [ ] **Integration**: Full pipeline flow works end-to-end

## FA v1 Gap Mitigations (Quick Reference)

| Gap | Issue | Where Implemented |
|-----|-------|-------------------|
| G1 | SubAgent lifecycle hooks missing | `base_subagent.py` — `setup()`, `teardown()` |
| G2 | Agent state Machine has no guards | `base_agent.py` — `VALID_STATE_TRANSITIONS` |
| G3 | EventBus messages unsigned | `event_bus.py` — HMAC-SHA256 signing |
| G4 | Schema versioning undefined | `schemas.py` — `schema_version=1` on all 23 |
| G5 | KG dedup key missing | `schemas.py` — `KnowledgeUpdateRequest.dedup_key` |
| G6 | Channel fingerprint baseline timing | `schemas.py` — `ChannelFingerprint.status` Literals |
| G7 | WebSocket JWT scopes undefined | `config.py` — `WS_JWT_SCOPES` |
| G8 | MoA Level 2 scoring criteria missing | `config.py` — `MOA_SCORING_WEIGHTS` (sum=1.0) |
| G9 | WorkerError schema didn't exist | `schemas.py` — schema #23 with 6 error types |
| G10 | Test fixtures not standardised | `tests/fixtures/` — factories + InMemoryEventBus |

## Templates

See the `templates/` directory for ready-to-use code templates:
- `worker-template.md` — BaseWorker implementation pattern
- `agent-template.md` — BaseAgent with state machine
- `subagent-template.md` — BaseSubAgent pipeline pattern
- `testing-patterns.md` — Test fixture and async test patterns
