"""
GeoSupply AI — Decorators
FA v2 | Auto-instrumentation for workers, agents, and subagents.

These are stub implementations for Phase 0.
Full implementations will be built in Phase 1 with real logging/metrics.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================
# @tracer — Span creation per call
# ============================================================
def tracer(func: Callable) -> Callable:
    """Create a trace span for each call. Logs entry/exit with timing."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        name = f"{args[0].__class__.__name__}.{func.__name__}" if args else func.__name__
        start = time.monotonic()
        logger.debug("TRACE START: %s", name)
        try:
            result = await func(*args, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug("TRACE END: %s (%.1fms)", name, elapsed_ms)
            return result
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error("TRACE ERROR: %s (%.1fms): %s", name, elapsed_ms, exc)
            raise

    return wrapper


# ============================================================
# @cost_tracker — INR cost logging per span
# ============================================================
def cost_tracker(func: Callable) -> Callable:
    """Track and log INR cost from the result meta."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        if isinstance(result, dict):
            cost = result.get("meta", {}).get("cost_inr", 0.0)
            name = args[0].__class__.__name__ if args else "unknown"
            if cost > 0:
                logger.info("COST: %s spent ₹%.4f", name, cost)
        return result

    return wrapper


# ============================================================
# @retry — Exponential backoff on failure
# ============================================================
def retry(max_retries: int = 3, backoff_base: float = 2.0):
    """Retry with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    wait_s = min(backoff_base ** attempt, 30)
                    logger.warning(
                        "RETRY: %s attempt %d/%d failed, waiting %.1fs: %s",
                        func.__name__, attempt, max_retries, wait_s, exc,
                    )
                    await asyncio.sleep(wait_s)
            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator


# ============================================================
# @timeout — Kill if exceeds time limit
# ============================================================
def timeout(seconds: int = 60):
    """Cancel if function exceeds timeout."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)

        return wrapper
    return decorator


# ============================================================
# @breaker — Circuit breaker for external API calls
# ============================================================
class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is OPEN."""
    pass


class _CircuitBreakerState:
    """Per-function circuit breaker state."""

    def __init__(self, max_failures: int = 5, open_seconds: int = 60):
        self.max_failures = max_failures
        self.open_seconds = open_seconds
        self.failures = 0
        self.state: str = "CLOSED"         # CLOSED, OPEN, HALF_OPEN
        self.opened_at: float | None = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.max_failures:
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker OPEN after %d failures", self.failures
            )

    def record_success(self) -> None:
        self.failures = 0
        self.state = "CLOSED"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            elapsed = time.monotonic() - (self.opened_at or 0)
            if elapsed >= self.open_seconds:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker HALF_OPEN (probing)")
                return True
            return False
        # HALF_OPEN: allow one attempt
        return True


def breaker(func: Callable) -> Callable:
    """Circuit breaker for external API calls."""
    cb = _CircuitBreakerState()

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not cb.can_execute():
            raise CircuitBreakerOpen(f"{func.__name__}: circuit breaker is OPEN")
        try:
            result = await func(*args, **kwargs)
            cb.record_success()
            return result
        except Exception as exc:
            cb.record_failure()
            raise

    wrapper._circuit_breaker = cb  # expose for testing/monitoring
    return wrapper


# ============================================================
# @internal_breaker — For Tier-3+ agent calls (v10)
# ============================================================
def internal_breaker(timeout_s: int = 30, max_failures: int = 3):
    """Circuit breaker for internal Tier-3+ agent calls."""

    def decorator(func: Callable) -> Callable:
        cb = _CircuitBreakerState(max_failures=max_failures, open_seconds=300)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not cb.can_execute():
                raise CircuitBreakerOpen(
                    f"{func.__name__}: internal circuit breaker is OPEN"
                )
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_s
                )
                cb.record_success()
                return result
            except asyncio.TimeoutError:
                cb.record_failure()
                raise
            except Exception as exc:
                cb.record_failure()
                raise

        wrapper._circuit_breaker = cb
        return wrapper
    return decorator
