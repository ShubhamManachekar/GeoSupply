---
name: api-rate-limiters
description: Logical rules for handling real API connections, exponential backoff, circuit breaking, and block detection without mocks.
---

# API Rate Limiters Skill (FA v2)

## Context
GeoSupply AI relies on 59 external APIs. Handling their rate limits, connection failures, and unannounced blocks is paramount for intelligence integrity. This skill emphasizes the **No Mocks** philosophy (Rule 16) for handling these limits.

## The `@breaker` Decorator
-   All external `process()` functions **MUST** use the `@breaker` decorator.
-   **Example**: `@breaker(timeout_s=30, max_failures=3)`
-   When testing the breaker, **NEVER mock the exceptions**. Use real fault injection, like querying an unrouteable IP (`192.0.2.1`) to verify `TimeoutError` translates to the `OPEN` breaker state.
-   **HALF_OPEN State Testing**: Do not mock `time.sleep()`. Actually wait the mandatory seconds or use `open_seconds=0` for immediate state transition testing during unit tests.

## Block Detection Pattern (R21)
APIs like OpenSky can ban IPs silently.
1.  Monitor `HTTP 403 Forbidden` limits.
2.  Extract `X-Rate-Limit-Remaining` headers from valid `aiohttp` responses.
3.  If rate limited or blocked, the worker MUST throw a structured `WorkerError(error_type="API_BLOCKED", message="X-Rate-Limit exceeded")`. No bare exceptions.

## Caching Strategy
Do not constantly hit APIs for duplicate runs.
-   Implement SQLite-based TTL (Time-To-Live) caching inside workers.
-   **TTL Windows**: 15 minutes for dynamic data (Markets), 1 hour for News, 6 hours for Disaster/Geology.
-   Database reads are allowed during testing; do NOT inject `AsyncMock` here.
