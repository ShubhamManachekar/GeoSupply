"""Tests for API HTTP schemas (schemas_api.py)."""

import pytest
from pydantic import ValidationError

from geosupply.api.schemas_api import (
    HealthResponse,
    DeepHealthResponse,
    TaskSubmitRequest,
    TaskSubmitResponse,
    PipelineStatusResponse,
    BriefRequest,
    BriefResponse,
    WorkerListResponse,
    AgentListResponse,
    SupervisorListResponse,
    BudgetStatusResponse,
    KGQueryRequest,
    KGQueryResponse,
    AuditStatusResponse,
    AuditRunResponse,
)


class TestHealthSchemas:
    def test_health_response_valid(self):
        r = HealthResponse(status="ok", environment="test")
        assert r.status == "ok"
        assert r.version == "0.1.0"

    def test_deep_health_response_valid(self):
        r = DeepHealthResponse(status="ok", environment="test", supervisors_registered=14)
        assert r.supervisors_registered == 14


class TestTaskSchemas:
    def test_task_submit_request_valid(self):
        r = TaskSubmitRequest(task_type="INGEST_NEWS", budget_inr=10.0)
        assert r.task_type == "INGEST_NEWS"
        assert r.priority == "P1"

    def test_task_submit_request_budget_zero_fails(self):
        with pytest.raises(ValidationError):
            TaskSubmitRequest(task_type="INGEST_NEWS", budget_inr=0.0)

    def test_task_submit_request_budget_over_500_fails(self):
        with pytest.raises(ValidationError):
            TaskSubmitRequest(task_type="INGEST_NEWS", budget_inr=501.0)

    def test_task_submit_request_invalid_priority_fails(self):
        with pytest.raises(ValidationError):
            TaskSubmitRequest(task_type="INGEST_NEWS", priority="P5")  # type: ignore[arg-type]

    def test_task_submit_response_valid(self):
        r = TaskSubmitResponse(
            task_id="t1",
            status="queued",
            supervisor="IngestionSupervisor",
            estimated_cost_inr=0.0,
        )
        assert r.status == "queued"

    def test_pipeline_status_response_valid(self):
        r = PipelineStatusResponse(task_id="t1", status="completed")
        assert r.status == "completed"


class TestBriefSchemas:
    def test_brief_request_valid(self):
        r = BriefRequest(payload={"region": "INDIA"}, budget_inr=50.0)
        assert r.budget_inr == 50.0

    def test_brief_request_negative_budget_fails(self):
        with pytest.raises(ValidationError):
            BriefRequest(budget_inr=-1.0)

    def test_brief_response_valid(self):
        r = BriefResponse(plan_id="p1", task_results={}, total_cost_inr=0.5)
        assert r.plan_id == "p1"


class TestWorkerSchemas:
    def test_worker_list_response_valid(self):
        r = WorkerListResponse(workers=["NewsWorker"], count=1)
        assert r.count == 1

    def test_agent_list_response_valid(self):
        r = AgentListResponse(agents=["LoggingAgent"], count=1)
        assert r.count == 1

    def test_supervisor_list_response_valid(self):
        r = SupervisorListResponse(supervisors=["IngestionSupervisor"], count=1)
        assert r.count == 1


class TestBudgetSchemas:
    def test_budget_status_response_valid(self):
        r = BudgetStatusResponse(
            cap_inr=500.0,
            reserved_inr=0.0,
            remaining_inr=500.0,
            alert_level="NORMAL",
        )
        assert r.cap_inr == 500.0

    def test_budget_status_invalid_alert_level_fails(self):
        with pytest.raises(ValidationError):
            BudgetStatusResponse(
                cap_inr=500.0,
                reserved_inr=0.0,
                remaining_inr=500.0,
                alert_level="UNKNOWN_LEVEL",  # type: ignore[arg-type]
            )


class TestKGSchemas:
    def test_kg_query_request_valid(self):
        r = KGQueryRequest(entity="India", depth=1)
        assert r.entity == "India"

    def test_kg_query_depth_zero_fails(self):
        with pytest.raises(ValidationError):
            KGQueryRequest(entity="India", depth=0)

    def test_kg_query_depth_four_fails(self):
        with pytest.raises(ValidationError):
            KGQueryRequest(entity="India", depth=4)

    def test_kg_query_response_valid(self):
        r = KGQueryResponse(entity="India", triples=[], node_count=0, trace_id="t1")
        assert r.entity == "India"


class TestAuditSchemas:
    def test_audit_status_response_valid(self):
        r = AuditStatusResponse(
            workers_discovered=19,
            agents_discovered=11,
            subagents_discovered=13,
            schema_count=32,
        )
        assert r.workers_discovered == 19

    def test_audit_run_response_valid(self):
        r = AuditRunResponse(passed=5, failed=0, categories_run=["breakage", "logic"])
        assert r.passed == 5
