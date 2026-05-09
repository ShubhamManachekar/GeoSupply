"""
Unit tests for all 13 domain agent modules (Session 29).
3 tests per agent class: valid structure, trace_id propagation, empty payload.
"""
from __future__ import annotations

import asyncio
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def _assert_valid_structure(result: dict, agent_name: str) -> None:
    assert "result" in result, f"{agent_name}: missing 'result' key"
    assert "meta" in result, f"{agent_name}: missing 'meta' key"
    meta = result["meta"]
    assert meta.get("cost_inr", -1) >= 0.0, f"{agent_name}: cost_inr < 0"
    ts = meta.get("timestamp", "")
    assert "T" in ts or len(ts) > 10, f"{agent_name}: timestamp not ISO"


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion agents
# ─────────────────────────────────────────────────────────────────────────────

class TestNewsAgent:
    def setup_method(self):
        from geosupply.agents.ingestion_agents import NewsAgent
        self.agent = NewsAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"query": "india trade"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "NewsAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "NewsAgent")


class TestIndiaAPIAgent:
    def setup_method(self):
        from geosupply.agents.ingestion_agents import IndiaAPIAgent
        self.agent = IndiaAPIAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "IndiaAPIAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "IndiaAPIAgent")


class TestTelegramAgent:
    def setup_method(self):
        from geosupply.agents.ingestion_agents import TelegramAgent
        self.agent = TelegramAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "TelegramAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "TelegramAgent")


class TestAISAgent:
    def setup_method(self):
        from geosupply.agents.ingestion_agents import AISAgent
        self.agent = AISAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "AISAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "AISAgent")


# ─────────────────────────────────────────────────────────────────────────────
# NLP agents
# ─────────────────────────────────────────────────────────────────────────────

class TestSentimentAgent:
    def setup_method(self):
        from geosupply.agents.nlp_agents import SentimentAgent
        self.agent = SentimentAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "India port closed"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "SentimentAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"text": "hello", "trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "SentimentAgent")


class TestNERAgent:
    def setup_method(self):
        from geosupply.agents.nlp_agents import NERAgent
        self.agent = NERAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "Mumbai port delayed"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "NERAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"text": "hello", "trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "NERAgent")


class TestClaimAgent:
    def setup_method(self):
        from geosupply.agents.nlp_agents import ClaimAgent
        self.agent = ClaimAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "Supply is disrupted"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "ClaimAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"text": "hello", "trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "ClaimAgent")


class TestTranslationAgent:
    def setup_method(self):
        from geosupply.agents.nlp_agents import TranslationAgent
        self.agent = TranslationAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "बंदरगाह बंद है"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "TranslationAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"text": "hello", "trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "TranslationAgent")


class TestPropagandaAgent:
    def setup_method(self):
        from geosupply.agents.nlp_agents import PropagandaAgent
        self.agent = PropagandaAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "enemy propaganda"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "PropagandaAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"text": "hello", "trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "PropagandaAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Quality agents
# ─────────────────────────────────────────────────────────────────────────────

class TestNLPAgent:
    def setup_method(self):
        from geosupply.agents.quality_agents import NLPAgent
        self.agent = NLPAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "supply chain risk"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "NLPAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "NLPAgent")


class TestHallucinationAgent:
    def setup_method(self):
        from geosupply.agents.quality_agents import HallucinationAgent
        self.agent = HallucinationAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"text": "some text"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "HallucinationAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "HallucinationAgent")


class TestSourceCredAgent:
    def setup_method(self):
        from geosupply.agents.quality_agents import SourceCredAgent
        self.agent = SourceCredAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"url": "https://example.com"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "SourceCredAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "SourceCredAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Intel agents
# ─────────────────────────────────────────────────────────────────────────────

class TestSupplierAgent:
    def setup_method(self):
        from geosupply.agents.intel_agents import SupplierAgent
        self.agent = SupplierAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"vendor": "Acme"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "SupplierAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "SupplierAgent")


class TestSanctionsAgent:
    def setup_method(self):
        from geosupply.agents.intel_agents import SanctionsAgent
        self.agent = SanctionsAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"entity": "Test Corp"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "SanctionsAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "SanctionsAgent")


class TestCyberAgent:
    def setup_method(self):
        from geosupply.agents.intel_agents import CyberAgent
        self.agent = CyberAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "CyberAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "CyberAgent")


class TestVerifierAgent:
    def setup_method(self):
        from geosupply.agents.intel_agents import VerifierAgent
        self.agent = VerifierAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"claim": "ports closed"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "VerifierAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "VerifierAgent")


class TestAuthorAgent:
    def setup_method(self):
        from geosupply.agents.intel_agents import AuthorAgent
        self.agent = AuthorAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "AuthorAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "AuthorAgent")


# ─────────────────────────────────────────────────────────────────────────────
# ML agents
# ─────────────────────────────────────────────────────────────────────────────

class TestStressScoreAgent:
    def setup_method(self):
        from geosupply.agents.ml_agents import StressScoreAgent
        self.agent = StressScoreAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "StressScoreAgent")
        assert "stress_score" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_stress_score_in_range(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        score = r["result"]["stress_score"]
        assert 0.0 <= score <= 1.0


class TestConflictPredictAgent:
    def setup_method(self):
        from geosupply.agents.ml_agents import ConflictPredictAgent
        self.agent = ConflictPredictAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "ConflictPredictAgent")
        assert "conflict_risk" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_conflict_risk_in_range(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        risk = r["result"]["conflict_risk"]
        assert 0.0 <= risk <= 1.0


class TestSupplierRankAgent:
    def setup_method(self):
        from geosupply.agents.ml_agents import SupplierRankAgent
        self.agent = SupplierRankAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "SupplierRankAgent")
        assert "ranked_vendors" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "SupplierRankAgent")


class TestSanctionClassifyAgent:
    def setup_method(self):
        from geosupply.agents.ml_agents import SanctionClassifyAgent
        self.agent = SanctionClassifyAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "SanctionClassifyAgent")
        assert "classification" in r["result"]

    def test_classification_is_valid_enum(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        assert r["result"]["classification"] in {"BLOCKED", "WATCHLIST", "CLEAR"}

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


# ─────────────────────────────────────────────────────────────────────────────
# India agents
# ─────────────────────────────────────────────────────────────────────────────

class TestIndiaPortAgent:
    def setup_method(self):
        from geosupply.agents.india_agents import IndiaPortAgent
        self.agent = IndiaPortAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "IndiaPortAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "IndiaPortAgent")


class TestIndiaMonsoonAgent:
    def setup_method(self):
        from geosupply.agents.india_agents import IndiaMonsoonAgent
        self.agent = IndiaMonsoonAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "IndiaMonsoonAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "IndiaMonsoonAgent")


class TestIndiaULIPAgent:
    def setup_method(self):
        from geosupply.agents.india_agents import IndiaULIPAgent
        self.agent = IndiaULIPAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "IndiaULIPAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "IndiaULIPAgent")


class TestIndiaPoliticalAgent:
    def setup_method(self):
        from geosupply.agents.india_agents import IndiaPoliticalAgent
        self.agent = IndiaPoliticalAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"text": "Modi announced new policy", "trace_id": "t1"}))
        _assert_valid_structure(r, "IndiaPoliticalAgent")
        assert "political_risk" in r["result"]

    def test_political_risk_in_range(self):
        r = _run(self.agent.execute({"text": "Elections delayed in India", "trace_id": "t1"}))
        risk = r["result"]["political_risk"]
        assert 0.0 <= risk <= 1.0

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard agents
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricPullAgent:
    def setup_method(self):
        from geosupply.agents.dashboard_agents import MetricPullAgent
        self.agent = MetricPullAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "MetricPullAgent")
        assert "metrics" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "MetricPullAgent")


class TestAlertRenderAgent:
    def setup_method(self):
        from geosupply.agents.dashboard_agents import AlertRenderAgent
        self.agent = AlertRenderAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"minutes": 60}, "trace_id": "t1"}))
        _assert_valid_structure(r, "AlertRenderAgent")
        assert "alerts" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "AlertRenderAgent")


class TestKPIUpdateAgent:
    def setup_method(self):
        from geosupply.agents.dashboard_agents import KPIUpdateAgent
        self.agent = KPIUpdateAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "KPIUpdateAgent")
        assert "monthly_cost_inr" in r["result"]
        assert "error_rate" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "KPIUpdateAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Dev agents
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaMigrateAgent:
    def setup_method(self):
        from geosupply.agents.dev_agents import SchemaMigrateAgent
        self.agent = SchemaMigrateAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "SchemaMigrateAgent")
        assert "valid_count" in r["result"]

    def test_valid_count_positive(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        assert r["result"]["valid_count"] > 0

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


@pytest.mark.slow
class TestLintCheckAgent:
    def setup_method(self):
        from geosupply.agents.dev_agents import LintCheckAgent
        self.agent = LintCheckAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "LintCheckAgent")
        assert "violation_count" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "LintCheckAgent")


class TestTestRunAgent:
    def setup_method(self):
        from geosupply.agents.dev_agents import TestRunAgent
        self.agent = TestRunAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"path": "tests/unit/"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "TestRunAgent")
        assert "passed" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "TestRunAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Test agents
# ─────────────────────────────────────────────────────────────────────────────

class TestUnitTestAgent:
    def setup_method(self):
        from geosupply.agents.test_agents import UnitTestAgent
        self.agent = UnitTestAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "UnitTestAgent")
        assert "passed" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "UnitTestAgent")


class TestIntegrationTestAgent:
    def setup_method(self):
        from geosupply.agents.test_agents import IntegrationTestAgent
        self.agent = IntegrationTestAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "IntegrationTestAgent")
        assert "passed" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "IntegrationTestAgent")


class TestCoverageAgent:
    def setup_method(self):
        from geosupply.agents.test_agents import CoverageAgent
        self.agent = CoverageAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "CoverageAgent")
        assert "percent_covered" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "CoverageAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Tech agents
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIHealthAgent:
    def setup_method(self):
        from geosupply.agents.tech_agents import APIHealthAgent
        self.agent = APIHealthAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"endpoints": []}, "trace_id": "t1"}))
        _assert_valid_structure(r, "APIHealthAgent")
        assert "endpoints" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "APIHealthAgent")


class TestDBCheckAgent:
    def setup_method(self):
        from geosupply.agents.tech_agents import DBCheckAgent
        self.agent = DBCheckAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "DBCheckAgent")
        assert "journal_mode" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "DBCheckAgent")


class TestCacheFlushAgent:
    def setup_method(self):
        from geosupply.agents.tech_agents import CacheFlushAgent
        self.agent = CacheFlushAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "CacheFlushAgent")
        assert "cleared_functions" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "CacheFlushAgent")


# ─────────────────────────────────────────────────────────────────────────────
# Marketing agents
# ─────────────────────────────────────────────────────────────────────────────

class TestTweetGenAgent:
    def setup_method(self):
        from geosupply.agents.marketing_agents import TweetGenAgent
        self.agent = TweetGenAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"text": "India port congestion", "trace_id": "t1"}))
        _assert_valid_structure(r, "TweetGenAgent")
        assert "tweet" in r["result"]

    def test_tweet_under_280_chars(self):
        r = _run(self.agent.execute({"text": "India port congestion worsens", "trace_id": "t1"}))
        assert r["result"]["char_count"] <= 280

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


class TestPredictionPostAgent:
    def setup_method(self):
        from geosupply.agents.marketing_agents import PredictionPostAgent
        self.agent = PredictionPostAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"text": "supply disrupted", "trace_id": "t1"}))
        _assert_valid_structure(r, "PredictionPostAgent")
        assert "prediction" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "PredictionPostAgent")


class TestAnalyticsAgent:
    def setup_method(self):
        from geosupply.agents.marketing_agents import AnalyticsAgent
        self.agent = AnalyticsAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "AnalyticsAgent")
        assert "total_tasks_24h" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "AnalyticsAgent")


class TestContentGenAgent:
    def setup_method(self):
        from geosupply.agents.marketing_agents import ContentGenAgent
        self.agent = ContentGenAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"text": "India port closed due to storms", "trace_id": "t1"}))
        _assert_valid_structure(r, "ContentGenAgent")
        assert "risk_level" in r["result"]

    def test_risk_level_valid_enum(self):
        r = _run(self.agent.execute({"text": "test", "trace_id": "t1"}))
        assert r["result"]["risk_level"] in {"HIGH", "MEDIUM", "LOW"}

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


# ─────────────────────────────────────────────────────────────────────────────
# Loophole agents
# ─────────────────────────────────────────────────────────────────────────────

class TestLoopholeHunterAgent:
    def setup_method(self):
        from geosupply.agents.loophole_agents import LoopholeHunterAgent
        self.agent = LoopholeHunterAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "LoopholeHunterAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "LoopholeHunterAgent")


class TestPenTestAgent:
    def setup_method(self):
        from geosupply.agents.loophole_agents import PenTestAgent
        self.agent = PenTestAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "PenTestAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "PenTestAgent")


class TestOverrideMonitorAgent:
    def setup_method(self):
        from geosupply.agents.loophole_agents import OverrideMonitorAgent
        self.agent = OverrideMonitorAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "OverrideMonitorAgent")

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "OverrideMonitorAgent")


# ─────────────────────────────────────────────────────────────────────────────
# DR agents
# ─────────────────────────────────────────────────────────────────────────────

class TestBackupAgent:
    def setup_method(self):
        from geosupply.agents.dr_agents import BackupAgent
        self.agent = BackupAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "BackupAgent")
        assert "backup_created" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "BackupAgent")


class TestCostProjectionAgent:
    def setup_method(self):
        from geosupply.agents.dr_agents import CostProjectionAgent
        self.agent = CostProjectionAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "CostProjectionAgent")
        assert "projected_monthly_inr" in r["result"]

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_handles_empty_payload(self):
        r = _run(self.agent.execute({}))
        _assert_valid_structure(r, "CostProjectionAgent")


class TestRestoreAgent:
    def setup_method(self):
        from geosupply.agents.dr_agents import RestoreAgent
        self.agent = RestoreAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"payload": {"backup_path": "/nonexistent.db"}, "trace_id": "t1"}))
        _assert_valid_structure(r, "RestoreAgent")
        assert "restored" in r["result"]

    def test_nonexistent_path_returns_error(self):
        r = _run(self.agent.execute({"payload": {"backup_path": "/nonexistent.db"}, "trace_id": "t1"}))
        assert r["result"]["restored"] is False
        assert r["result"]["error"] is not None

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"


class TestFailoverAgent:
    def setup_method(self):
        from geosupply.agents.dr_agents import FailoverAgent
        self.agent = FailoverAgent()

    def test_execute_returns_valid_structure(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        _assert_valid_structure(r, "FailoverAgent")
        assert r["result"]["failover_triggered"] is True

    def test_propagates_trace_id(self):
        r = _run(self.agent.execute({"trace_id": "test-trace"}))
        assert r["meta"]["trace_id"] == "test-trace"

    def test_backup_result_included(self):
        r = _run(self.agent.execute({"trace_id": "t1"}))
        assert "backup_result" in r["result"]
