"""
GeoSupply AI — HTTP API schemas (Phase 9).

Pydantic v2 request/response models for the FastAPI REST layer.
These are HTTP envelope types — separate from internal geosupply/schemas.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    version: str = "0.1.0"
    environment: str
    timestamp: datetime = Field(default_factory=_utcnow)


class DeepHealthResponse(HealthResponse):
    supervisors_registered: int = 0
    budget_remaining_inr: float = 0.0
    workers_count: int = 0
    agents_count: int = 0


class TaskSubmitRequest(BaseModel):
    task_type: str
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    budget_inr: float = Field(default=10.0, gt=0.0, le=500.0)
    payload: dict = Field(default_factory=dict)
    timeout_s: int = Field(default=60, ge=1, le=600)


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: Literal["queued", "rejected"]
    supervisor: str
    estimated_cost_inr: float
    queued_at: datetime = Field(default_factory=_utcnow)
    reject_reason: str | None = None


class PipelineStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "running", "completed", "error", "rejected", "skipped"]
    result: dict | None = None
    cost_inr: float = 0.0


class BriefRequest(BaseModel):
    payload: dict = Field(default_factory=dict)
    plan_id: str | None = None
    budget_inr: float = Field(default=50.0, gt=0.0, le=500.0)


class BriefResponse(BaseModel):
    plan_id: str
    task_results: dict
    total_cost_inr: float
    generated_at: datetime = Field(default_factory=_utcnow)


class WorkerListResponse(BaseModel):
    workers: list[str]
    count: int


class AgentListResponse(BaseModel):
    agents: list[str]
    count: int


class SupervisorListResponse(BaseModel):
    supervisors: list[str]
    count: int


class BudgetStatusResponse(BaseModel):
    cap_inr: float
    reserved_inr: float
    remaining_inr: float
    alert_level: Literal["NORMAL", "WARN", "ALERT", "CRITICAL"]


class KGQueryRequest(BaseModel):
    entity: str
    depth: int = Field(default=1, ge=1, le=3)
    trace_id: str = ""


class KGQueryResponse(BaseModel):
    entity: str
    triples: list[dict]
    node_count: int
    trace_id: str


class AuditStatusResponse(BaseModel):
    workers_discovered: int
    agents_discovered: int
    subagents_discovered: int
    schema_count: int
    last_run_at: datetime | None = None


class AuditRunResponse(BaseModel):
    passed: int
    failed: int
    categories_run: list[str]
    run_at: datetime = Field(default_factory=_utcnow)
