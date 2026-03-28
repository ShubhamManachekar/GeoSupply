---
name: swarm-orchestrator
description: SwarmMaster v10 design and implementation — task decomposition, DAG dependency resolution, MoE expert routing, budget gating, degraded mode, and health-aware dispatch for GeoSupply's Layer 1 orchestrator.
---

# Swarm Orchestrator — SwarmMaster v10

> Custom GeoSupply skill — Layer 1 orchestrator implementation guide

## SwarmMaster Responsibilities

```
1. Receive top-level tasks from Layer 0 (Human / Admin)
2. Decompose tasks into a DAG of subtasks
3. Route each subtask to the optimal expert (via MoERouterAgent)
4. Gate all task dispatch through BudgetManagerAgent
5. Monitor execution health (via HealthCheckAgent)
6. Aggregate results and return structured output
7. Activate degraded mode when agents fail
8. Publish task lifecycle events to EventBus
```

---

## 1. Task Decomposition (DAG)

```python
from dataclasses import dataclass, field

@dataclass
class TaskNode:
    task_id: str
    action: str
    agent_type: str           # Which agent class handles this
    tier: LLMTier
    dependencies: list[str]   # task_ids that must complete first
    budget_inr: float         # Allocated budget for this node
    timeout_seconds: int = 120
    retry_count: int = 0

class SwarmMasterAgent(BaseAgent):
    """Layer 1 orchestrator — owns task DAG and execution lifecycle."""
    name = "swarm_master"
    tier = LLMTier.MEDIUM_14B

    async def _decompose(self, task: TaskPacket) -> list[TaskNode]:
        """Break top-level task into dependency-ordered subtasks."""
        # Example: "Analyze India pharma supply chain risk"
        # → Node 1: NewsWorker (ingest) [no deps]
        # → Node 2: NERWorker (entities) [depends: Node 1]
        # → Node 3: ClaimWorker (claims) [depends: Node 1]
        # → Node 4: KnowledgeGraphAgent (KG update) [depends: Node 2, 3]
        # → Node 5: RAGSubAgent (retrieval) [depends: Node 4]
        # → Node 6: BriefSynthSubAgent (synthesis) [depends: Node 5]
        # → Node 7: GeoRiskScoreAgent (score) [depends: Node 6]
        ...

    async def _execute_dag(self, nodes: list[TaskNode]) -> dict:
        """Execute DAG with parallel independent nodes, sequential dependencies."""
        completed: dict[str, dict] = {}
        while len(completed) < len(nodes):
            ready = [n for n in nodes
                     if n.task_id not in completed
                     and all(dep in completed for dep in n.dependencies)]
            if not ready:
                break  # DAG deadlock — raise error
            results = await asyncio.gather(*[
                self._dispatch(n, completed) for n in ready
            ], return_exceptions=True)
            for node, result in zip(ready, results):
                completed[node.task_id] = result
        return completed
```

---

## 2. MoE Expert Selection

```python
async def _route_to_expert(self, task_node: TaskNode) -> BaseAgent:
    """Select optimal agent via MoERouterAgent."""
    routing_request = {
        "required_capabilities": task_node.capabilities,
        "tier_preference": task_node.tier,
        "budget_remaining_inr": await self.budget_agent.get_remaining(),
        "exclude_agents": self._unhealthy_agents,
    }
    expert_id = await self.moe_router.execute("select_expert", routing_request)
    return self._agent_registry[expert_id["selected_agent"]]
```

---

## 3. Budget Gating

```python
async def _budget_gate(self, node: TaskNode) -> bool:
    """Check budget before dispatching any task."""
    approval = await self.budget_agent.execute("approve_spend", {
        "amount_inr": node.budget_inr,
        "tier": node.tier.value,
        "task_id": node.task_id,
    })
    if not approval["approved"]:
        await self._activate_degraded_mode(reason="budget_exhausted")
        return False
    return True
```

---

## 4. Degraded Mode (v10 Enhancement)

```python
# Degraded mode activation triggers:
DEGRADED_TRIGGERS = [
    "budget_exhausted",       # BudgetManager blocks Tier-3
    "agent_health_critical",  # HealthCheck shows agent failing
    "pipeline_sla_breach",    # PIPELINE_SLA_MINUTES = 12 exceeded
    "circuit_breaker_open",   # External API circuit breaker opened
]

# Degraded mode behaviour by tier:
DEGRADED_FALLBACKS = {
    LLMTier.LARGE_20B: LLMTier.MEDIUM_14B,  # Downgrade Tier-3 → Tier-2
    LLMTier.MEDIUM_14B: LLMTier.SMALL_3B,   # Downgrade Tier-2 → Tier-1
    LLMTier.SMALL_3B: LLMTier.CPU_ONLY,     # Tier-1 → STATIC decoder only
}

async def _activate_degraded_mode(self, reason: str) -> None:
    self._degraded = True
    self._degraded_reason = reason
    await self.event_bus.publish("swarm.degraded", AgentMessage(
        sender_id=self.id, payload={"reason": reason, "timestamp": now()}
    ))
    logger.warning("SwarmMaster entering degraded mode: %s", reason)
```

---

## 5. Task Lifecycle Events

```python
# Events published by SwarmMaster to EventBus
SWARM_EVENTS = {
    "swarm.task.received":   "Task accepted from Layer 0",
    "swarm.task.decomposed": "DAG created, N nodes",
    "swarm.task.dispatched": "Node dispatched to expert",
    "swarm.task.completed":  "Node completed, cost tracked",
    "swarm.task.failed":     "Node failed, retry or fallback",
    "swarm.task.done":       "Full DAG completed, result ready",
    "swarm.degraded":        "Degraded mode activated",
    "swarm.recovered":       "Degraded mode cleared",
}
```

---

## 6. Health-Aware Dispatch

```python
async def _refresh_health_registry(self) -> None:
    """Poll HealthCheckAgent before each DAG execution."""
    health = await self.health_agent.execute("check_all", {})
    self._unhealthy_agents = {
        agent_id for agent_id, status in health["agents"].items()
        if status["state"] in ("ERROR", "RECOVERY")
    }

# Always exclude unhealthy agents from routing
```

---

## 7. SwarmMaster Implementation Checklist

- [ ] Inherits `BaseAgent`, sets `on_critical_path = True`
- [ ] `_decompose()` returns valid DAG (no circular dependencies)
- [ ] `_execute_dag()` detects deadlock and raises `DAGDeadlockError`
- [ ] Budget gate checked BEFORE every node dispatch
- [ ] Degraded mode tested: budget exhaustion, agent failure, SLA breach
- [ ] All events published with HMAC signature
- [ ] Parallel independent nodes executed with `asyncio.gather`
- [ ] Test: full 7-node pipeline happy path
- [ ] Test: budget exhaustion mid-pipeline (nodes 1-3 complete, 4-7 blocked)
- [ ] Test: agent failure triggers degraded + fallback tier
- [ ] Test: DAG deadlock detected and raises error (not hangs)

---

## 8. MAX_PARALLEL_SESSIONS = 6 (LOCKED)

```python
# From config.py — never exceed 6 concurrent SwarmMaster sessions
# Enforced via asyncio.Semaphore in the HTTP gateway layer
SWARM_SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_SESSIONS)
```

---

## Related Skills
- `supervisor-designer` — Supervisors between SwarmMaster and agents
- `agent-designer` — Agent implementations SwarmMaster dispatches to
- `budget-controller` — Budget gate implementation detail
- `phase-gate-auditor` — Audit SwarmMaster before phase gate closure
