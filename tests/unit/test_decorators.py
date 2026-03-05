"""Unit tests for decorators — tracer, cost_tracker, retry, timeout, breaker."""

import asyncio
import pytest
from geosupply.core.decorators import (
    tracer, cost_tracker, retry, timeout, breaker, internal_breaker,
    CircuitBreakerOpen,
)


class FakeComponent:
    """Fake class to test decorators that read self.__class__.__name__."""
    pass


class TestTracer:
    @pytest.mark.asyncio
    async def test_tracer_passes_through(self):
        @tracer
        async def go(self):
            return 42

        result = await go(FakeComponent())
        assert result == 42

    @pytest.mark.asyncio
    async def test_tracer_propagates_exception(self):
        @tracer
        async def fail(self):
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            await fail(FakeComponent())


class TestCostTracker:
    @pytest.mark.asyncio
    async def test_cost_tracker_logs_cost(self):
        @cost_tracker
        async def work(self):
            return {"meta": {"cost_inr": 0.05}}

        result = await work(FakeComponent())
        assert result["meta"]["cost_inr"] == 0.05

    @pytest.mark.asyncio
    async def test_cost_tracker_no_meta(self):
        @cost_tracker
        async def work(self):
            return "not a dict"

        result = await work(FakeComponent())
        assert result == "not a dict"


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_succeeds_first_try(self):
        call_count = 0

        @retry(max_retries=3, backoff_base=0.01)
        async def work():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await work()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second(self):
        call_count = 0

        @retry(max_retries=3, backoff_base=0.01)
        async def work():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("fail")
            return "ok"

        result = await work()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self):
        @retry(max_retries=2, backoff_base=0.01)
        async def work():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            await work()


class TestTimeout:
    @pytest.mark.asyncio
    async def test_fast_function_passes(self):
        @timeout(seconds=5)
        async def fast():
            return "fast"

        result = await fast()
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_slow_function_times_out(self):
        @timeout(seconds=1)
        async def slow():
            await asyncio.sleep(10)
            return "slow"

        with pytest.raises(asyncio.TimeoutError):
            await slow()


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_breaker_passes_on_success(self):
        @breaker
        async def work():
            return "ok"

        result = await work()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_breaker_opens_after_failures(self):
        call_count = 0

        @breaker
        async def work():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        # Trigger 5 failures (default max_failures=5)
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await work()

        # 6th call should get CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            await work()

    @pytest.mark.asyncio
    async def test_breaker_state_exposed(self):
        @breaker
        async def work():
            return "ok"

        assert work._circuit_breaker.state == "CLOSED"
        await work()
        assert work._circuit_breaker.state == "CLOSED"


class TestInternalBreaker:
    @pytest.mark.asyncio
    async def test_internal_breaker_passes(self):
        @internal_breaker(timeout_s=5, max_failures=2)
        async def work():
            return "ok"

        result = await work()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_internal_breaker_timeout(self):
        @internal_breaker(timeout_s=1, max_failures=2)
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(asyncio.TimeoutError):
            await slow()


class TestCircuitBreakerHalfOpen:
    """L142-144, L147: Test HALF_OPEN probe after timeout."""

    @pytest.mark.asyncio
    async def test_breaker_transitions_to_half_open(self):
        """After OPEN timeout, breaker enters HALF_OPEN and allows one probe."""
        import time
        from geosupply.core.decorators import _CircuitBreakerState

        cb = _CircuitBreakerState(max_failures=2, open_seconds=0)  # 0s = instant
        cb.record_failure()
        cb.record_failure()  # Now OPEN
        assert cb.state == "OPEN"

        # With open_seconds=0, it should immediately transition to HALF_OPEN
        time.sleep(0.01)
        assert cb.can_execute() is True
        assert cb.state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self):
        """Successful call during HALF_OPEN closes the breaker."""
        from geosupply.core.decorators import _CircuitBreakerState

        cb = _CircuitBreakerState(max_failures=2, open_seconds=0)
        cb.record_failure()
        cb.record_failure()
        cb.can_execute()  # Triggers HALF_OPEN
        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.failures == 0

    @pytest.mark.asyncio
    async def test_half_open_allows_execution(self):
        """HALF_OPEN state returns True from can_execute."""
        from geosupply.core.decorators import _CircuitBreakerState

        cb = _CircuitBreakerState(max_failures=1, open_seconds=0)
        cb.record_failure()  # OPEN
        import time; time.sleep(0.01)
        assert cb.can_execute() is True  # HALF_OPEN
        assert cb.state == "HALF_OPEN"
        assert cb.can_execute() is True  # HALF_OPEN still allows


class TestInternalBreakerFailures:
    """L182, L194-196: internal_breaker failure path and open state."""

    @pytest.mark.asyncio
    async def test_internal_breaker_non_timeout_failure(self):
        """Non-timeout exception records failure."""
        @internal_breaker(timeout_s=5, max_failures=2)
        async def fail():
            raise ValueError("bad value")

        with pytest.raises(ValueError):
            await fail()
        assert fail._circuit_breaker.failures == 1

    @pytest.mark.asyncio
    async def test_internal_breaker_opens_after_max(self):
        """After max_failures, internal breaker opens."""
        @internal_breaker(timeout_s=5, max_failures=2)
        async def fail():
            raise ValueError("bad")

        for _ in range(2):
            with pytest.raises(ValueError):
                await fail()

        assert fail._circuit_breaker.state == "OPEN"
        with pytest.raises(CircuitBreakerOpen):
            await fail()
