"""Tests for NLPSupervisor — Phase 6 NLP pipeline supervisor."""

import pytest
from geosupply.supervisors.nlp_supervisor import NLPSupervisor
from geosupply.schemas import TaskPacket


@pytest.fixture
def supervisor():
    return NLPSupervisor()


def make_task(task_type: str, budget: float = 5.0, payload: dict | None = None) -> TaskPacket:
    return TaskPacket(
        task_id=f"nlp-{task_type.lower()}",
        task_type=task_type,
        priority="P1",
        budget_inr=budget,
        payload=payload or {"text": "Test NLP input"},
    )


def _dispatched_agent(result: dict) -> str:
    """Extract agent name from completed dispatch result."""
    return result["result"]["result"]["agent"]


class TestRouting:
    async def test_sentiment_task_routes_to_sentiment_agent(self, supervisor):
        task = make_task("NLP_SENTIMENT")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SentimentAgent"

    async def test_ner_task_routes_to_ner_agent(self, supervisor):
        task = make_task("NLP_NER")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "NERAgent"

    async def test_claim_task_routes_to_claim_agent(self, supervisor):
        task = make_task("NLP_CLAIM")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "ClaimAgent"

    async def test_translate_task_routes_to_translation_agent(self, supervisor):
        task = make_task("NLP_TRANSLATE")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "TranslationAgent"

    async def test_propaganda_task_routes_to_propaganda_agent(self, supervisor):
        task = make_task("NLP_PROPAGANDA")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "PropagandaAgent"

    async def test_unknown_task_type_falls_back_to_sentiment(self, supervisor):
        task = make_task("NLP_UNKNOWN_XYZ")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SentimentAgent"

    async def test_nlp_any_routes_to_sentiment(self, supervisor):
        task = make_task("NLP_ANY")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"
        assert _dispatched_agent(result) == "SentimentAgent"


class TestBudgetGating:
    async def test_task_within_budget_dispatched(self, supervisor):
        task = make_task("NLP_SENTIMENT", budget=5.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    async def test_task_over_budget_rejected(self, supervisor):
        task = make_task("NLP_SENTIMENT", budget=100.0)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "task_over_budget"

    async def test_budget_exhausted_after_many_dispatches(self, supervisor):
        dispatched = 0
        rejected = 0
        for i in range(20):
            task = make_task("NLP_SENTIMENT", budget=0.5)
            result = await supervisor.dispatch(task)
            if result["status"] == "completed":
                dispatched += 1
            else:
                rejected += 1
        assert dispatched + rejected == 20


class TestCapabilities:
    def test_capable_agents_for_sentiment(self, supervisor):
        agents = supervisor.capable_agents("SENTIMENT_ANALYSIS")
        assert "SentimentAgent" in agents

    def test_capable_agents_for_ner(self, supervisor):
        agents = supervisor.capable_agents("ENTITY_EXTRACTION")
        assert "NERAgent" in agents

    def test_capable_agents_for_unknown_returns_empty(self, supervisor):
        agents = supervisor.capable_agents("UNKNOWN_CAPABILITY_XYZ")
        assert agents == []


class TestSupervisorMeta:
    def test_name_is_nlp_supervisor(self, supervisor):
        assert supervisor.name == "NLPSupervisor"

    def test_domain_is_nlp(self, supervisor):
        assert supervisor.domain == "nlp"

    def test_budget_is_8(self, supervisor):
        assert supervisor.budget_inr == 8.0

    def test_five_agents_registered(self, supervisor):
        assert len(supervisor.agents) == 5
