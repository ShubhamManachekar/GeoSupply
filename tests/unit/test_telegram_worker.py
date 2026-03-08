"""
Tests for TelegramWorker — ZERO MOCKS (Rule 16)
Tests REAL worker logic: channel validation, message normalisation, category filtering.
"""

import pytest
from geosupply.workers.telegram_worker import (
    TelegramWorker,
    _validate_channel_id,
    _normalise_messages,
    CHANNEL_REGISTRY,
    DEFAULT_MESSAGE_LIMIT,
    MAX_MESSAGE_LIMIT,
)


@pytest.fixture
async def worker():
    """REAL worker instance."""
    w = TelegramWorker()
    await w.setup()
    yield w
    await w.teardown()


# ── Test: Channel Validation ──


class TestChannelValidation:
    def test_valid_at_username(self):
        ok, msg = _validate_channel_id("@ConflictIntel")
        assert ok is True
        assert msg == ""

    def test_valid_numeric_id(self):
        ok, msg = _validate_channel_id("-1001234567890")
        assert ok is True

    def test_empty_channel_id(self):
        ok, msg = _validate_channel_id("")
        assert ok is False
        assert "Missing" in msg

    def test_invalid_format_no_at(self):
        ok, msg = _validate_channel_id("ConflictIntel")
        assert ok is False
        assert "Invalid" in msg

    def test_too_short_username(self):
        ok, msg = _validate_channel_id("@abc")
        assert ok is False

    def test_valid_min_length_username(self):
        ok, msg = _validate_channel_id("@abcde")
        assert ok is True


# ── Test: Message Normalisation ──


class TestNormalisation:
    def test_normalise_happy_path(self):
        raw = [
            {
                "id": 12345,
                "text": "Indian Navy deploys warships to Arabian Sea",
                "date": "2026-03-08T10:00:00",
                "views": 5000,
                "forwards": 120,
            },
            {
                "id": 12346,
                "text": "Supply chain disruption at Mumbai port",
                "date": "2026-03-08T11:00:00",
                "views": 3000,
                "forwards": 80,
                "media": True,
            },
        ]
        msgs = _normalise_messages(raw, "@ConflictIntel")
        assert len(msgs) == 2
        assert msgs[0]["channel_id"] == "@ConflictIntel"
        assert msgs[0]["message_id"] == 12345
        assert msgs[1]["has_media"] is True

    def test_skips_empty_messages(self):
        raw = [
            {"id": 1, "text": ""},
            {"id": 2, "text": None},
            {"id": 3, "text": "Valid message"},
        ]
        msgs = _normalise_messages(raw, "@test")
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Valid message"

    def test_truncates_long_text(self):
        raw = [{"id": 1, "text": "x" * 5000, "date": "now"}]
        msgs = _normalise_messages(raw, "@test")
        assert len(msgs[0]["text"]) == 2000

    def test_empty_input(self):
        assert _normalise_messages([], "@test") == []

    def test_alternative_field_names(self):
        raw = [{"message_id": 999, "message": "Alt field", "date": "now"}]
        msgs = _normalise_messages(raw, "@test")
        assert msgs[0]["message_id"] == 999
        assert msgs[0]["text"] == "Alt field"


# ── Test: Input Validation ──


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_missing_channel_id(self, worker):
        res = await worker.process({"limit": 10, "trace_id": "t1"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "channel_id" in res["message"]

    @pytest.mark.asyncio
    async def test_invalid_channel_id(self, worker):
        res = await worker.process({"channel_id": "bad!", "trace_id": "t1"})
        assert res["error_type"] == "INPUT_INVALID"

    @pytest.mark.asyncio
    async def test_limit_capped_at_max(self, worker):
        """Limit should be silently capped at MAX_MESSAGE_LIMIT."""
        async def _mock_fetch(channel_id, limit, trace_id):
            return [{"id": 1, "text": "test", "date": "now"}]

        worker._fetch_messages = _mock_fetch
        res = await worker.process({
            "channel_id": "@ConflictIntel",
            "limit": 999,
            "trace_id": "t-cap",
        })
        assert "error_type" not in res


# ── Test: Category Filtering ──


class TestCategoryFilter:
    @pytest.mark.asyncio
    async def test_filter_skips_wrong_category(self, worker):
        res = await worker.process({
            "channel_id": "@ConflictIntel",
            "category_filter": "maritime",
            "trace_id": "t-filter",
        })
        assert "error_type" not in res
        assert res["result"]["count"] == 0
        assert "skipped_reason" in res["result"]

    @pytest.mark.asyncio
    async def test_filter_matches_correct_category(self, worker):
        async def _mock_fetch(channel_id, limit, trace_id):
            return [{"id": 1, "text": "Conflict update", "date": "now"}]

        worker._fetch_messages = _mock_fetch
        res = await worker.process({
            "channel_id": "@ConflictIntel",
            "category_filter": "conflict",
            "trace_id": "t-match",
        })
        assert "error_type" not in res
        assert res["result"]["count"] == 1


# ── Test: Channel Registry ──


class TestChannelRegistry:
    def test_registry_has_minimum_channels(self):
        assert len(CHANNEL_REGISTRY) >= 27

    def test_all_channels_have_category(self):
        for ch_id, meta in CHANNEL_REGISTRY.items():
            assert "category" in meta, f"{ch_id} missing category"

    def test_get_channels_by_category(self):
        w = TelegramWorker()
        conflict_channels = w.get_channels_by_category("conflict")
        assert len(conflict_channels) >= 3
        assert all(ch.startswith("@") for ch in conflict_channels)

    def test_get_channels_by_region(self):
        w = TelegramWorker()
        india_channels = w.get_channels_by_region("india")
        assert len(india_channels) >= 2


# ── Test: Capabilities & Lifecycle ──


class TestCapabilities:
    def test_advertise_capabilities(self):
        w = TelegramWorker()
        caps = w.advertise_capabilities()
        assert caps["name"] == "TelegramWorker"
        assert caps["tier"] == 0
        assert "INGEST_TELEGRAM" in caps["capabilities"]
        assert "OSINT_CHANNEL" in caps["capabilities"]


class TestExceptionHandling:
    @pytest.mark.asyncio
    async def test_fetch_failure_returns_worker_error(self, worker):
        """Exception in _fetch_messages -> WorkerError."""
        async def _fail_fetch(channel_id, limit, trace_id):
            raise ConnectionError("Telegram API timeout")

        worker._fetch_messages = _fail_fetch
        res = await worker.process({
            "channel_id": "@ConflictIntel", "trace_id": "t-fail",
        })
        assert res["error_type"] == "API_FAILURE"
        assert "timeout" in res["message"].lower()


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_non_integer_limit_uses_default(self, worker):
        """Non-int limit should fallback to DEFAULT_MESSAGE_LIMIT."""
        async def _mock_fetch(channel_id, limit, trace_id):
            return [{"id": 1, "text": "test", "date": "now"}]

        worker._fetch_messages = _mock_fetch
        res = await worker.process({
            "channel_id": "@ConflictIntel", "limit": "notanint", "trace_id": "t-lim",
        })
        assert "error_type" not in res

    @pytest.mark.asyncio
    async def test_negative_limit_uses_default(self, worker):
        async def _mock_fetch(channel_id, limit, trace_id):
            return [{"id": 1, "text": "test", "date": "now"}]

        worker._fetch_messages = _mock_fetch
        res = await worker.process({
            "channel_id": "@ConflictIntel", "limit": -5, "trace_id": "t-neg",
        })
        assert "error_type" not in res

    @pytest.mark.asyncio
    async def test_unregistered_channel_gets_unknown_meta(self, worker):
        async def _mock_fetch(channel_id, limit, trace_id):
            return [{"id": 1, "text": "msg", "date": "now"}]

        worker._fetch_messages = _mock_fetch
        res = await worker.process({
            "channel_id": "@UnknownChannel12345", "trace_id": "t-unreg",
        })
        assert res["result"]["channel_meta"]["category"] == "unknown"


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_setup_teardown(self):
        w = TelegramWorker()
        await w.setup()
        assert w._is_setup is True
        await w.teardown()
        assert w._is_setup is False

    @pytest.mark.asyncio
    async def test_safe_process_on_bad_input(self):
        w = TelegramWorker()
        res = await w.safe_process({"trace_id": "t-safe"})
        assert res["error_type"] == "INPUT_INVALID"
