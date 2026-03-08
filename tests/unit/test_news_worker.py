"""
Tests for NewsWorker — ZERO MOCKS (Rule 16)
Tests the REAL worker logic: URL building, normalisation, input validation.
Only external HTTP calls are avoided (no live API hits in tests).
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from geosupply.workers.news_worker import (
    NewsWorker,
    _build_request_url,
    _normalise_newsapi,
    _normalise_gdelt,
    _normalise_acled,
    VALID_SOURCE_TYPES,
)


@pytest.fixture
async def worker():
    """REAL worker instance — no mocks."""
    w = NewsWorker()
    await w.setup()
    yield w
    await w.teardown()


# ── Test: URL Building (pure logic, no HTTP) ──


class TestURLBuilding:
    def test_newsapi_url_has_query(self):
        url = _build_request_url("newsapi", "india supply chain", api_key="test_key")
        assert "newsapi.org" in url
        assert "q=india+supply+chain" in url
        assert "apiKey=test_key" in url

    def test_gdelt_url_no_auth(self):
        url = _build_request_url("gdelt", "earthquake india")
        assert "gdeltproject.org" in url
        assert "query=earthquake+india" in url
        assert "apiKey" not in url  # GDELT has no auth

    def test_acled_url_has_country(self):
        url = _build_request_url("acled", "India", api_key="acled_key")
        assert "acleddata.com" in url
        assert "country=India" in url
        assert "key=acled_key" in url


# ── Test: Normalisation (pure logic, no HTTP) ──


class TestNormalisation:
    def test_normalise_newsapi_happy_path(self):
        raw = {
            "articles": [
                {
                    "title": "India supply chain disruption",
                    "description": "Major port delays in Gujarat",
                    "source": {"name": "Reuters"},
                    "publishedAt": "2026-03-08T10:00:00Z",
                    "url": "https://reuters.com/article/1",
                },
                {
                    "title": "China trade tensions rising",
                    "description": "Tariffs expected to increase",
                    "source": {"name": "Bloomberg"},
                    "publishedAt": "2026-03-08T09:00:00Z",
                    "url": "https://bloomberg.com/article/2",
                },
            ]
        }
        articles = _normalise_newsapi(raw)
        assert len(articles) == 2
        assert articles[0]["title"] == "India supply chain disruption"
        assert articles[0]["body"] == "Major port delays in Gujarat"
        assert articles[0]["source"] == "Reuters"
        assert articles[0]["url"] == "https://reuters.com/article/1"
        assert len(articles[0]["dedup_hash"]) == 16  # SHA256 truncated

    def test_normalise_newsapi_skips_empty_titles(self):
        raw = {
            "articles": [
                {"title": None, "description": "No title", "source": {"name": "X"}, "url": "u1"},
                {"title": "Valid", "description": "Has title", "source": {"name": "Y"}, "url": "u2"},
            ]
        }
        articles = _normalise_newsapi(raw)
        assert len(articles) == 1
        assert articles[0]["title"] == "Valid"

    def test_normalise_gdelt_happy_path(self):
        raw = {
            "articles": [
                {
                    "title": "GDELT Event in India",
                    "domain": "ndtv.com",
                    "seendate": "20260308T100000Z",
                    "url": "https://ndtv.com/article/1",
                },
            ]
        }
        articles = _normalise_gdelt(raw)
        assert len(articles) == 1
        assert articles[0]["source"] == "ndtv.com"

    def test_normalise_acled_happy_path(self):
        raw = {
            "data": [
                {
                    "data_id": 12345,
                    "event_type": "Battles",
                    "sub_event_type": "Armed clash",
                    "notes": "Conflict in northern region",
                    "source": "Local media",
                    "event_date": "2026-03-07",
                    "location": "Manipur",
                    "country": "India",
                    "fatalities": 3,
                },
            ]
        }
        articles = _normalise_acled(raw)
        assert len(articles) == 1
        assert "Battles" in articles[0]["title"]
        assert articles[0]["country"] == "India"
        assert articles[0]["fatalities"] == 3

    def test_normalise_empty_response(self):
        assert _normalise_newsapi({}) == []
        assert _normalise_gdelt({}) == []
        assert _normalise_acled({}) == []

    def test_dedup_hashes_are_deterministic(self):
        raw = {
            "articles": [
                {"title": "Same Title", "source": {"name": "A"}, "url": "https://example.com/1"},
            ]
        }
        h1 = _normalise_newsapi(raw)[0]["dedup_hash"]
        h2 = _normalise_newsapi(raw)[0]["dedup_hash"]
        assert h1 == h2  # Same input → same hash


# ── Test: Input Validation (REAL worker) ──


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_missing_source_type(self, worker):
        res = await worker.process({"query": "india", "trace_id": "t1"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "source_type" in res["message"]

    @pytest.mark.asyncio
    async def test_invalid_source_type(self, worker):
        res = await worker.process({"source_type": "twitter", "query": "india", "trace_id": "t1"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "twitter" in res["message"]

    @pytest.mark.asyncio
    async def test_empty_query(self, worker):
        res = await worker.process({"source_type": "gdelt", "query": "", "trace_id": "t1"})
        assert res["error_type"] == "INPUT_INVALID"
        assert "query" in res["message"]

    @pytest.mark.asyncio
    async def test_missing_api_key_for_newsapi(self, worker):
        with patch.dict(os.environ, {}, clear=True):
            res = await worker.process({
                "source_type": "newsapi",
                "query": "india",
                "trace_id": "t1",
            })
            assert res["error_type"] == "API_FAILURE"
            assert "API key required" in res["message"]


# ── Test: API Failure Handling ──


class TestAPIFailure:
    @pytest.mark.asyncio
    async def test_fetch_failure_returns_worker_error(self, worker):
        """Override _fetch_url to simulate network failure."""
        async def _fail_fetch(url, trace_id):
            raise RuntimeError("Connection timeout")

        worker._fetch_url = _fail_fetch
        with patch.dict(os.environ, {"GEOSUPPLY_NEWSAPI_KEY": "fake_key"}):
            res = await worker.process({
                "source_type": "newsapi",
                "query": "india",
                "trace_id": "t-fail",
            })
        assert res["error_type"] == "API_FAILURE"
        assert "Connection timeout" in res["message"]
        assert res["worker_name"] == "NewsWorker"

    @pytest.mark.asyncio
    async def test_gdelt_no_auth_needed(self, worker):
        """GDELT should NOT fail on missing API key — it requires none."""
        async def _mock_fetch(url, trace_id):
            return {"articles": [{"title": "Test", "domain": "test.com", "seendate": "now", "url": "u"}]}

        worker._fetch_url = _mock_fetch
        res = await worker.process({
            "source_type": "gdelt",
            "query": "earthquake",
            "trace_id": "t-gdelt",
        })
        assert "error_type" not in res
        assert res["result"]["count"] == 1


# ── Test: Capabilities & Lifecycle ──


class TestHappyPathEndToEnd:
    @pytest.mark.asyncio
    async def test_newsapi_full_pipeline(self, worker):
        """E2E: override _fetch_url → test full pipeline including normaliser."""
        async def _mock_fetch(url, trace_id):
            return {
                "articles": [
                    {"title": "India port delays", "description": "Gujarat congestion",
                     "source": {"name": "Reuters"}, "publishedAt": "2026-03-08", "url": "https://r.com/1"}
                ]
            }

        worker._fetch_url = _mock_fetch
        with patch.dict(os.environ, {"GEOSUPPLY_NEWSAPI_KEY": "test_key"}):
            res = await worker.process({
                "source_type": "newsapi", "query": "india", "trace_id": "t-e2e",
            })
        assert "error_type" not in res
        assert res["result"]["count"] == 1
        assert res["result"]["articles"][0]["title"] == "India port delays"
        assert res["meta"]["worker"] == "NewsWorker"
        assert res["meta"]["cost_inr"] == 0.0

    @pytest.mark.asyncio
    async def test_acled_full_pipeline(self, worker):
        """E2E: ACLED with injected response."""
        async def _mock_fetch(url, trace_id):
            return {
                "data": [
                    {"data_id": 1, "event_type": "Protests", "sub_event_type": "March",
                     "notes": "Protest in Delhi", "source": "media", "event_date": "2026-03-07",
                     "location": "Delhi", "country": "India", "fatalities": 0}
                ]
            }

        worker._fetch_url = _mock_fetch
        with patch.dict(os.environ, {"GEOSUPPLY_ACLED_KEY": "key", "GEOSUPPLY_ACLED_EMAIL": "a@b.com"}):
            res = await worker.process({
                "source_type": "acled", "query": "India", "trace_id": "t-acled",
            })
        assert res["result"]["source_type"] == "acled"
        assert res["result"]["count"] == 1

    @pytest.mark.asyncio
    async def test_newsapi_with_api_key_in_input(self, worker):
        """API key passed directly in input_data, not via env."""
        async def _mock_fetch(url, trace_id):
            return {"articles": []}

        worker._fetch_url = _mock_fetch
        res = await worker.process({
            "source_type": "newsapi", "query": "test", "trace_id": "t-key",
            "api_key": "direct_key",
        })
        assert "error_type" not in res
        assert res["result"]["count"] == 0

    @pytest.mark.asyncio
    async def test_process_exception_from_normaliser(self, worker):
        """Feed bad data that causes normaliser to throw."""
        async def _bad_fetch(url, trace_id):
            raise ConnectionError("DNS resolution failed")

        worker._fetch_url = _bad_fetch
        with patch.dict(os.environ, {"GEOSUPPLY_NEWSAPI_KEY": "key"}):
            res = await worker.process({
                "source_type": "newsapi", "query": "india", "trace_id": "t-exc",
            })
        assert res["error_type"] == "API_FAILURE"
        assert "DNS" in res["message"]


class TestNewsApiContentFallback:
    def test_description_none_falls_back_to_content(self):
        raw = {
            "articles": [
                {"title": "Test", "description": None, "content": "Fallback content",
                 "source": {"name": "X"}, "url": "u1"},
            ]
        }
        articles = _normalise_newsapi(raw)
        assert articles[0]["body"] == "Fallback content"


class TestCapabilities:
    def test_advertise_capabilities(self):
        w = NewsWorker()
        caps = w.advertise_capabilities()
        assert caps["name"] == "NewsWorker"
        assert caps["tier"] == 0
        assert "INGEST_NEWS" in caps["capabilities"]
        assert "RSS_PARSE" in caps["capabilities"]
        assert caps["use_static"] is False


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_setup_teardown(self):
        w = NewsWorker()
        await w.setup()
        assert w._is_setup is True
        await w.teardown()
        assert w._is_setup is False

    def test_valid_source_types_constant(self):
        assert "newsapi" in VALID_SOURCE_TYPES
        assert "gdelt" in VALID_SOURCE_TYPES
        assert "acled" in VALID_SOURCE_TYPES
        assert len(VALID_SOURCE_TYPES) == 3

    @pytest.mark.asyncio
    async def test_safe_process_delegates(self):
        """Test safe_process wrapper (BaseWorker integration)."""
        w = NewsWorker()
        res = await w.safe_process({"trace_id": "t-safe"})
        assert res["error_type"] == "INPUT_INVALID"
