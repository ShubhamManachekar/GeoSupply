"""Worker, agent, and supervisor registry endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from geosupply.api.schemas_api import WorkerListResponse, AgentListResponse, SupervisorListResponse
from geosupply.core.base_worker import BaseWorker
from geosupply.core.base_agent import BaseAgent
from geosupply.core.base_supervisor import BaseSupervisor

router = APIRouter()


@router.get("/workers", response_model=WorkerListResponse)
async def list_workers():
    """List all registered worker classes."""
    names = sorted(c.__name__ for c in BaseWorker.__subclasses__())
    return WorkerListResponse(workers=names, count=len(names))


@router.get("/agents", response_model=AgentListResponse)
async def list_agents():
    """List all registered agent classes."""
    names = sorted(c.__name__ for c in BaseAgent.__subclasses__())
    return AgentListResponse(agents=names, count=len(names))


@router.get("/supervisors", response_model=SupervisorListResponse)
async def list_supervisors():
    """List all registered supervisor classes."""
    names = sorted(c.__name__ for c in BaseSupervisor.__subclasses__())
    return SupervisorListResponse(supervisors=names, count=len(names))
