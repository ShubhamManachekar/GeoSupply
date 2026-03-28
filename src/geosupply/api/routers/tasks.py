"""Task submission and status endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from geosupply.api.schemas_api import TaskSubmitRequest, TaskSubmitResponse, PipelineStatusResponse
from geosupply.api.dependencies import swarm_master_dep, task_store_dep
from geosupply.orchestrator.swarm_master import ROUTING_TABLE
from geosupply.schemas import TaskPacket

router = APIRouter()


@router.post("", response_model=TaskSubmitResponse, status_code=202)
async def submit_task(
    body: TaskSubmitRequest,
    sm=Depends(swarm_master_dep),
    task_store: dict = Depends(task_store_dep),
):
    """Submit a task for execution via the swarm."""
    task_id = str(uuid.uuid4())
    supervisor_name, _tier, _uses_static = ROUTING_TABLE.get(
        body.task_type, ("IngestionSupervisor", 0, False)
    )

    packet = TaskPacket(
        task_id=task_id,
        task_type=body.task_type,
        priority=body.priority,
        budget_inr=body.budget_inr,
        timeout_s=body.timeout_s,
        payload=body.payload,
    )

    result = await sm.route(packet)
    status = "queued" if result.get("status") == "completed" else "rejected"
    task_store[task_id] = {
        "task_id": task_id,
        "status": "completed" if status == "queued" else result.get("status", "rejected"),
        "result": result.get("result"),
        "cost_inr": result.get("cost_inr", 0.0),
    }

    return TaskSubmitResponse(
        task_id=task_id,
        status=status,
        supervisor=supervisor_name,
        estimated_cost_inr=result.get("cost_inr", 0.0),
        reject_reason=result.get("reason") if status == "rejected" else None,
    )


@router.get("/{task_id}", response_model=PipelineStatusResponse)
async def get_task_status(
    task_id: str,
    task_store: dict = Depends(task_store_dep),
):
    """Retrieve the status of a previously submitted task."""
    entry = task_store.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"task_id {task_id!r} not found")
    return PipelineStatusResponse(**entry)
