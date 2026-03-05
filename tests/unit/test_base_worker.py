"""Unit tests for BaseWorker — lifecycle, safe_process, WorkerError."""

import asyncio
import pytest
from geosupply.core.base_worker import BaseWorker
from geosupply.schemas import WorkerError


class GoodWorker(BaseWorker):
    name = "GoodWorker"
    tier = 0
    capabilities = {"TEST"}

    async def process(self, input_data: dict) -> dict:
        return {
            "result": {"value": 42},
            "meta": {"worker": self.name, "tier": self.tier, "cost_inr": 0.01},
        }


class FailWorker(BaseWorker):
    name = "FailWorker"
    tier = 1
    capabilities = {"FAIL"}
    max_retries = 1

    async def process(self, input_data: dict) -> dict:
        raise RuntimeError("intentional failure")


class SlowWorker(BaseWorker):
    name = "SlowWorker"
    tier = 0
    capabilities = {"SLOW"}
    max_retries = 0
    timeout_seconds = 1

    async def process(self, input_data: dict) -> dict:
        await asyncio.sleep(10)
        return {"result": {}, "meta": {"worker": self.name, "tier": 0, "cost_inr": 0.0}}


class TestBaseWorkerLifecycle:
    @pytest.mark.asyncio
    async def test_setup_marks_ready(self):
        w = GoodWorker()
        assert not w._is_setup
        await w.setup()
        assert w._is_setup

    @pytest.mark.asyncio
    async def test_teardown_resets(self):
        w = GoodWorker()
        await w.setup()
        await w.teardown()
        assert not w._is_setup


class TestBaseWorkerProcess:
    @pytest.mark.asyncio
    async def test_good_worker_returns_result(self):
        w = GoodWorker()
        result = await w.safe_process({"trace_id": "t1"})
        assert result["result"]["value"] == 42
        assert result["meta"]["cost_inr"] == 0.01

    @pytest.mark.asyncio
    async def test_safe_process_auto_setup(self):
        w = GoodWorker()
        assert not w._is_setup
        await w.safe_process({"trace_id": "t1"})
        assert w._is_setup


class TestBaseWorkerErrorHandling:
    @pytest.mark.asyncio
    async def test_fail_worker_returns_worker_error(self):
        w = FailWorker()
        result = await w.safe_process({"trace_id": "t2"})
        assert result["error_type"] == "INTERNAL"
        assert "intentional failure" in result["message"]
        assert result["worker_name"] == "FailWorker"
        assert result["trace_id"] == "t2"

    @pytest.mark.asyncio
    async def test_timeout_returns_worker_error(self):
        w = SlowWorker()
        result = await w.safe_process({"trace_id": "t3"})
        assert result["error_type"] == "TIMEOUT"
        assert result["worker_name"] == "SlowWorker"


class TestBaseWorkerCapabilities:
    def test_advertise(self):
        w = GoodWorker()
        caps = w.advertise_capabilities()
        assert caps["name"] == "GoodWorker"
        assert caps["tier"] == 0
        assert "TEST" in caps["capabilities"]
        assert caps["use_static"] is False

    def test_repr(self):
        w = GoodWorker()
        assert "GoodWorker" in repr(w)
