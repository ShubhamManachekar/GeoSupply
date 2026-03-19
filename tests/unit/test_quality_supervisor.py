"""Tests for QualitySupervisor."""

import pytest

from geosupply.config import HALLUCINATION_FLOOR
from geosupply.supervisors.quality_supervisor import QualitySupervisor
from geosupply.schemas import TaskPacket


def _make_task(
    task_type: str,
    budget_inr: float = 1.0,
    confidence: float | None = None,
) -> TaskPacket:
    payload: dict = {}
    if confidence is not None:
        payload["confidence"] = confidence
    return TaskPacket(
        task_id=f"t-{task_type.lower()}",
        task_type=task_type,
        budget_inr=budget_inr,
        priority="P1",
        payload=payload,
    )


@pytest.fixture
def supervisor():
    sup = QualitySupervisor()
    sup.reset_budget()
    return sup


class TestQualitySupervisorInit:
    def test_name_and_domain(self):
        sup = QualitySupervisor()
        assert sup.name == "QualitySupervisor"
        assert sup.domain == "quality"

    def test_budget_inr(self):
        sup = QualitySupervisor()
        assert sup.budget_inr == 10.0

    def test_hallucination_floor_property(self):
        sup = QualitySupervisor()
        assert sup.hallucination_floor == HALLUCINATION_FLOOR


class TestQualitySupervisorDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_nlp_enrich(self, supervisor):
        task = _make_task("NLP_ENRICH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_hallucination_check(self, supervisor):
        task = _make_task("HALLUCINATION_CHECK")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_dispatch_source_cred(self, supervisor):
        task = _make_task("SOURCE_CRED")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rejects_below_hallucination_floor(self, supervisor):
        task = _make_task("NLP_ENRICH", confidence=0.40)
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "below_hallucination_floor"
        assert result["floor"] == HALLUCINATION_FLOOR

    @pytest.mark.asyncio
    async def test_passes_at_exact_floor(self, supervisor):
        task = _make_task("NLP_ENRICH", confidence=HALLUCINATION_FLOOR)
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_passes_above_floor(self, supervisor):
        task = _make_task("NLP_ENRICH", confidence=0.90)
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_confidence_key_passes_through(self, supervisor):
        # Tasks without confidence key bypass floor check
        task = _make_task("NLP_ENRICH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_rejects_budget_exhausted(self, supervisor):
        supervisor._budget_remaining = 0.0
        task = _make_task("NLP_ENRICH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"
        assert result["reason"] == "budget_exhausted"

    @pytest.mark.asyncio
    async def test_rejects_when_paused(self, supervisor):
        supervisor.pause()
        task = _make_task("NLP_ENRICH")
        result = await supervisor.dispatch(task)
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_resumes_after_pause(self, supervisor):
        supervisor.pause()
        supervisor.resume()
        task = _make_task("SOURCE_CRED")
        result = await supervisor.dispatch(task)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_floor_check_before_budget_check(self, supervisor):
        # Floor check fires even if budget would also fail
        supervisor._budget_remaining = 0.0
        task = _make_task("NLP_ENRICH", confidence=0.30)
        result = await supervisor.dispatch(task)
        # Floor check fires first
        assert result["reason"] == "below_hallucination_floor"
