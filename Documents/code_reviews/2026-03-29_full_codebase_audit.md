<!-- markdownlint-disable MD013 MD022 MD032 -->

# Full Codebase Audit Report (CodeRabbit-Style)

Date: 2026-03-29 IST
Reviewer: GPT-5.3-Codex
Scope: Full repository connectivity + logic scan, strict audit gate, targeted placeholder and stub remediation.

## Findings (Ordered by Severity)

### 1) High — Supervisor default proxies can silently mask missing agent wiring
- Impact: If a supervisor is instantiated without explicit runtime `register_agent(...)` calls, `_SupervisorAgentProxy.safe_execute()` returns a synthetic successful payload (`status: stub_ok`) with zero cost. This can hide missing real agent wiring in production-like paths.
- Evidence:
  - `src/geosupply/supervisors/ingestion_supervisor.py`
  - `src/geosupply/supervisors/nlp_supervisor.py`
  - `src/geosupply/supervisors/quality_supervisor.py`
  - `src/geosupply/supervisors/intel_supervisor.py`
  - `src/geosupply/supervisors/infra_supervisor.py`
  - Session 28/29 additional supervisors follow same pattern.
- Recommendation:
  - Gate proxy execution behind explicit non-production mode, or return a structured error when proxy is still active in runtime.
  - Add a startup assertion in API/orchestrator bootstrap verifying no proxy instances remain for required domains.

### 2) Medium — Test suite still contains mixed mock patterns despite ZERO-MOCK policy intent
- Impact: Audit confidence is reduced by inconsistent policy interpretation across tests and fixtures.
- Evidence:
  - `tests/fixtures/mock_worker.py`
  - `tests/unit/test_watchdog_subagent.py`
  - `tests/unit/test_audit_cli.py`
  - Other tests monkeypatch internal fetch methods for network-dependent workers.
- Recommendation:
  - Clarify policy exception boundaries in one canonical test policy doc.
  - Prefer deterministic local fakes or in-memory adapters over `AsyncMock` for internal contracts.
  - Keep 3rd-party boundary mocking only where unavoidable.

### 3) Low — External dependency deprecation warning from ChromaDB telemetry path
- Impact: Non-blocking now, but likely future breakage on Python 3.16 if upstream not updated.
- Evidence:
  - strict-audit warnings include `chromadb.telemetry.opentelemetry` using deprecated `asyncio.iscoroutinefunction` path.
- Recommendation:
  - Pin/monitor compatible ChromaDB release.
  - Track upstream fix and remove warning suppression reliance.

### 4) Low — Pytest plugin rewrite warning (anyio)
- Impact: Noise in strict gate logs; no behavioral failure.
- Evidence:
  - strict-audit warning: module already imported cannot be rewritten.
- Recommendation:
  - Keep as known warning unless plugin/load order changes are planned.

## Remediations Applied in This Session

1. Replaced runtime placeholder logic in Telegram ingestion path with credential-aware Telethon flow and safe fallback behavior.
2. Replaced simulated extraction comments with deterministic event extraction heuristics and lifecycle state handling.
3. Removed stub semantics in BriefSynth and GraphRAG docs/comments.
4. Updated decorators header to match production reality.
5. Reduced pytest collection warnings by marking helper classes as non-tests in base-agent and base-supervisor tests.
6. Normalized supervisor layer terminology from `_StubAgent` to `_SupervisorAgentProxy`.

## Validation Evidence

- Focused tests: 64 passed.
- Supervisor suite: 196 passed.
- Strict gate: 5/5 checks passed.
- Full test suite: 963 passed.
- Warning count improved: 4 -> 2.

## Recommended Next Remediation Batch

1. Add runtime proxy guardrail (fail fast when proxy remains active for required supervisors).
2. Standardize ZERO-MOCK policy in tests with explicit allowlist for external boundaries.
3. Add a dedicated audit check for proxy presence in production boot path.
4. Track external warning debt (ChromaDB, anyio) in dependency maintenance plan.
