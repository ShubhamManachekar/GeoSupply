"""Knowledge graph query and update endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from geosupply.api.schemas_api import KGQueryResponse
from geosupply.agents.knowledge_graph_agent import KnowledgeGraphAgent

router = APIRouter()

_kg_agent = KnowledgeGraphAgent()


@router.get("/query", response_model=KGQueryResponse)
async def kg_query(
    entity: str = Query(..., min_length=1),
    depth: int = Query(default=1, ge=1, le=3),
    trace_id: str = Query(default=""),
):
    """Query the knowledge graph for triples related to an entity."""
    result = await _kg_agent.execute({
        "task_type": "KG_QUERY",
        "entity": entity,
        "depth": depth,
        "trace_id": trace_id,
    })
    data = result.get("result", {})
    triples = data.get("neighbours", [])
    return KGQueryResponse(
        entity=entity,
        triples=triples,
        node_count=len(triples),
        trace_id=trace_id,
    )


@router.post("/update", status_code=201)
async def kg_update(body: dict):
    """Add or update a triple in the knowledge graph."""
    result = await _kg_agent.execute({"task_type": "KG_ADD_TRIPLE", **body})
    return {"status": "created", "result": result.get("result", {})}
