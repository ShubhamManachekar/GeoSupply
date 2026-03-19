"""Tests for AuthorWorker — Tier-3 author attribution and bot detection."""

import pytest
from geosupply.workers.author_worker import AuthorWorker


@pytest.fixture
async def worker():
    w = AuthorWorker()
    await w.setup()
    yield w
    await w.teardown()


class TestHappyPath:
    async def test_human_formal_text(self, worker):
        result = await worker.process({
            "text": "According to analysis shows, data indicates that experts warn about the risk. Officials say the situation requires careful monitoring and assessment.",
            "trace_id": "t-001",
        })
        assert "result" in result
        assert result["result"]["author_type"] in {"HUMAN", "UNKNOWN", "BOT", "STATE_SPONSORED"}
        assert 0.0 <= result["result"]["attribution_confidence"] <= 1.0
        assert result["meta"]["cost_inr"] == 0.05

    async def test_state_sponsored_text(self, worker):
        result = await worker.process({
            "text": "xinhua reports that Western propaganda and imperialist hegemon violates sovereignty. Global Times confirms information warfare narrative control against our motherland.",
            "trace_id": "t-002",
        })
        assert result["result"]["author_type"] == "STATE_SPONSORED"
        assert result["result"]["attribution_confidence"] >= 0.40
        assert len(result["result"]["state_sponsor_indicators"]) > 0

    async def test_bot_text_with_cta(self, worker):
        result = await worker.process({
            "text": "BREAKING NEWS!!! Click share retweet subscribe like now follow us join us immediately!!! https://spam1.com https://spam2.com https://spam3.com",
            "trace_id": "t-003",
        })
        assert result["result"]["author_type"] == "BOT"
        assert result["result"]["bot_probability"] >= 0.45

    async def test_meta_fields_present(self, worker):
        result = await worker.process({
            "text": "A neutral informational sentence about supply chains.",
            "trace_id": "t-004",
        })
        meta = result["meta"]
        assert meta["worker"] == "AuthorWorker"
        assert meta["tier"] == 3
        assert meta["cost_inr"] == 0.05
        assert "timestamp" in meta

    async def test_language_register_detected(self, worker):
        result = await worker.process({
            "text": "tbh folks this is just my two cents imho lol ngl honestly just saying btw omg fwiw",
            "trace_id": "t-005",
        })
        assert result["result"]["language_register"] == "INFORMAL"


class TestErrorPaths:
    async def test_empty_text_returns_worker_error(self, worker):
        result = await worker.process({
            "text": "",
            "trace_id": "t-006",
        })
        assert result.get("error_type") == "INPUT_INVALID"

    async def test_missing_text_key_returns_worker_error(self, worker):
        result = await worker.process({"trace_id": "t-007"})
        assert result.get("error_type") == "INPUT_INVALID"

    async def test_sanitised_text_key_accepted(self, worker):
        result = await worker.process({
            "sanitised_text": "According to experts, the data indicates clear supply chain trends.",
            "trace_id": "t-008",
        })
        assert "result" in result
        assert "error_type" not in result


class TestStyleAnalysis:
    async def test_propaganda_register(self, worker):
        result = await worker.process({
            "text": "The sheeple are brainwashed by the woke globalist deep state cabal running the rigged puppet government!",
            "trace_id": "t-009",
        })
        assert result["result"]["language_register"] == "PROPAGANDA"

    async def test_technical_register(self, worker):
        result = await worker.process({
            "text": "The regression algorithm showed variance in the p-value coefficient. The GDP CAGR and EBITDA neural network analysis revealed significant correlation.",
            "trace_id": "t-010",
        })
        assert result["result"]["language_register"] == "TECHNICAL"

    async def test_style_markers_not_empty_for_flagged_text(self, worker):
        result = await worker.process({
            "text": "xinhua tass sputnik reports Western propaganda imperialist hegemon violates sovereignty motherland!!! CLICK SHARE LIKE NOW!!!",
            "trace_id": "t-011",
        })
        assert len(result["result"]["style_markers"]) > 0

    async def test_bot_probability_bounded(self, worker):
        result = await worker.process({
            "text": "Normal text about current events and supply chain issues in India.",
            "trace_id": "t-012",
        })
        assert 0.0 <= result["result"]["bot_probability"] <= 1.0

    async def test_state_sponsor_indicators_list(self, worker):
        result = await worker.process({
            "text": "Some article that mentions neither state media nor propaganda patterns.",
            "trace_id": "t-013",
        })
        assert isinstance(result["result"]["state_sponsor_indicators"], list)
