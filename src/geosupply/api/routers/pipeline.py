"""Pipeline status endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from geosupply.api.schemas_api import PipelineStatusResponse
from geosupply.api.dependencies import task_store_dep

router = APIRouter()


@router.get("/{task_id}", response_model=PipelineStatusResponse)
async def pipeline_status(
    task_id: str,
    task_store: dict = Depends(task_store_dep),
):
    """Get pipeline execution status for a task."""
    entry = task_store.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"task_id {task_id!r} not found")
    return PipelineStatusResponse(**entry)
