"""
GeoSupply AI — OSINT Source Base
TTL-cached, circuit-breaker-guarded connector contract.

Every connector fetches REAL data from a free public API (ZERO MOCKS rule —
graceful degradation, never fabricated data). On failure the last good
payload is served from cache and the failure is surfaced in SourceHealth.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, Field

from geosupply.osint.models import SourceHealth

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Conservative defaults — these are courtesy limits on free public APIs.
DEFAULT_TIMEOUT_S = 12.0
USER_AGENT = "GeoSupplyAI-OSINT/1.0 (+https://github.com/ShubhamManachekar/GeoSupply)"


class SourceResult(BaseModel, Generic[T]):
    """Outcome of one refresh cycle for a source."""
    name: str
    ok: bool
    items: list[Any] = Field(default_factory=list)
    error: str = ""
    latency_ms: float = 0.0
    fetched_at: datetime | None = None


class _Breaker:
    """Minimal async-safe circuit breaker (mirrors core.decorators semantics)."""

    def __init__(self, max_failures: int = 4, open_seconds: float = 180.0):
        self.max_failures = max_failures
        self.open_seconds = open_seconds
        self.failures = 0
        self.state = "CLOSED"
        self.opened_at: float | None = None

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.monotonic() - (self.opened_at or 0.0) >= self.open_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN: single probe allowed

    def record_success(self) -> None:
        self.failures = 0
        self.state = "CLOSED"

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.max_failures:
            self.state = "OPEN"
            self.opened_at = time.monotonic()


class BaseSource(ABC):
    """
    Contract for one upstream OSINT source.

    Subclasses implement `fetch(client)` returning a list of parsed items.
    `refresh(client)` adds: TTL cache, circuit breaker, latency tracking,
    and last-good-payload fallback.
    """

    name: str = "BaseSource"
    ttl_s: float = 120.0

    def __init__(self) -> None:
        self._breaker = _Breaker()
        self._cache: list[Any] = []
        self._cached_at: float = 0.0
        self._last_ok: bool = False
        self._last_error: str = ""
        self._last_latency_ms: float = 0.0
        self._last_refresh: datetime | None = None

    # ── subclass contract ─────────────────────────────────────────────
    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[Any]:
        """Fetch and parse fresh items from the upstream API."""

    # ── lifecycle ─────────────────────────────────────────────────────
    def cache_fresh(self) -> bool:
        # Use the populated flag (not bool(cache)) so a legitimate empty
        # result still satisfies the TTL instead of refetching every cycle.
        return self._cached_at > 0.0 and (time.monotonic() - self._cached_at) < self.ttl_s

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> SourceResult:
        """Refresh with TTL cache + breaker. Never raises — degrades to cache."""
        if not force and self.cache_fresh():
            # Report the true last-known health, not an optimistic True.
            return self._result(ok=self._last_ok, items=self._cache)

        if not self._breaker.can_execute():
            self._last_error = "circuit breaker OPEN"
            return self._result(ok=False, items=self._cache)

        start = time.monotonic()
        try:
            items = await self.fetch(client)
            self._last_latency_ms = (time.monotonic() - start) * 1000
            self._breaker.record_success()
            self._cache = items
            self._cached_at = time.monotonic()
            self._last_ok = True
            self._last_error = ""
            self._last_refresh = datetime.now(timezone.utc)
            return self._result(ok=True, items=items)
        except Exception as exc:  # noqa: BLE001 — boundary: log + degrade, never raise
            self._last_latency_ms = (time.monotonic() - start) * 1000
            self._breaker.record_failure()
            self._last_ok = False
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("OSINT source %s failed: %s", self.name, self._last_error)
            return self._result(ok=False, items=self._cache)

    def _result(self, ok: bool, items: list[Any]) -> SourceResult:
        return SourceResult(
            name=self.name,
            ok=ok,
            items=items,
            error=self._last_error,
            latency_ms=round(self._last_latency_ms, 1),
            fetched_at=self._last_refresh,
        )

    def health(self) -> SourceHealth:
        return SourceHealth(
            name=self.name,
            ok=self._last_ok,
            breaker_state=self._breaker.state,
            last_refresh=self._last_refresh,
            latency_ms=round(self._last_latency_ms, 1),
            items=len(self._cache),
            error=self._last_error,
        )


def http_headers() -> dict[str, str]:
    """Default headers for all OSINT fetches."""
    return {"User-Agent": USER_AGENT, "Accept": "*/*"}
