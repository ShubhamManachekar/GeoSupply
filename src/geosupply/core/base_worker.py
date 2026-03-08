"""
GeoSupply AI — BaseWorker
FA v2 | Part II | Layer 5

Every worker inherits from BaseWorker.
Provides lifecycle hooks, auto-instrumentation stubs,
circuit breakers, and retry policies.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from geosupply.schemas import WorkerError

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """
    Abstract base for all 45 workers (FA v2 census).

    LIFECYCLE:
        __init__()    → register capabilities + set retry policy
        setup()       → load models / connections (called once)
        process()     → do the work (called per task)
        teardown()    → cleanup (called on shutdown)

    INVARIANTS:
        - process() MUST return dict with 'result' and 'meta'
        - On failure, return WorkerError schema (G9)
        - meta MUST include cost_inr (always INR, never USD)
        - STATIC workers (use_static=True) must conform to Pydantic output
    """

    name: str = "BaseWorker"
    tier: int = 0                          # 0=CPU, 1=3b STATIC, 2=14b, 3=20b
    use_static: bool = False               # True = STATIC decoder mandatory
    capabilities: set[str] = set()
    max_retries: int = 3
    timeout_seconds: int = 60

    _is_setup: bool = False

    async def setup(self) -> None:
        """Called once before first process(). Load models, open connections."""
        self._is_setup = True

    @abstractmethod
    async def process(self, input_data: dict) -> dict:
        """
        Core work function.

        Args:
            input_data: Task-specific data dict. Must include 'trace_id'.

        Returns:
            dict with keys:
                'result': task output
                'meta': {'worker': str, 'tier': int, 'cost_inr': float, ...}

        On failure:
            WorkerError(...).model_dump()
        """
        ...

    async def teardown(self) -> None:
        """Called on graceful shutdown. Close connections, flush buffers."""
        self._is_setup = False

    def advertise_capabilities(self) -> dict:
        """Return capabilities for MoE routing."""
        return {
            "name": self.name,
            "tier": self.tier,
            "capabilities": sorted(self.capabilities),
            "use_static": self.use_static,
        }

    async def safe_process(self, input_data: dict) -> dict:
        """
        Wrapper around process() with error handling.
        Catches exceptions and returns WorkerError instead of crashing.
        """
        if not self._is_setup:
            await self.setup()

        trace_id = input_data.get("trace_id", "unknown")
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                result = await asyncio.wait_for(
                    self.process(input_data),
                    timeout=self.timeout_seconds,
                )
                return result

            except asyncio.TimeoutError:
                retry_count += 1
                logger.warning(
                    "%s: timeout (attempt %d/%d)",
                    self.name, retry_count, self.max_retries,
                )
                if retry_count > self.max_retries:
                    return WorkerError(
                        error_type="TIMEOUT",
                        message=f"Timed out after {self.timeout_seconds}s",
                        worker_name=self.name,
                        retry_count=retry_count,
                        trace_id=trace_id,
                    ).model_dump()

            except Exception as exc:
                retry_count += 1
                logger.error(
                    "%s: error (attempt %d/%d): %s",
                    self.name, retry_count, self.max_retries, exc,
                )
                if retry_count > self.max_retries:
                    return WorkerError(
                        error_type="INTERNAL",
                        message=str(exc),
                        worker_name=self.name,
                        retry_count=retry_count,
                        trace_id=trace_id,
                    ).model_dump()

                # Exponential backoff
                await asyncio.sleep(min(2 ** retry_count, 30))

        # Should not reach here, but safety net
        return WorkerError(
            error_type="INTERNAL",
            message="Exhausted all retries",
            worker_name=self.name,
            retry_count=retry_count,
            trace_id=trace_id,
        ).model_dump()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} tier={self.tier}>"
