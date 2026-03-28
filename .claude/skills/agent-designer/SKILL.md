---
name: agent-designer
description: Multi-agent system design for GeoSupply's 7-layer swarm. Covers agent role definition, communication patterns, state machines, DAG routing, MoE gating, and orchestration strategies aligned to FA v3.
---

# Agent Designer — GeoSupply Swarm Edition

> Upstream source: alirezarezvani/claude-skills · engineering/agent-designer
> Adapted for: GeoSupply FA v3, 7-layer DAG, MoE routing, HMAC-signed EventBus

## Architecture Topology (LOCKED)

```
Layer 0  Human / Admin
Layer 1  SwarmMaster (Orchestrator)
Layer 2  Supervisors (14 domain supervisors)
Layer 3  Agents (38 agents)
Layer 4  SubAgents (13 RAG/QA pipelines)
Layer 5  Workers (45 atomic tasks)
Layer 6  Model & Skill Pool
Layer 7  LoopholeHunter (cross-cutting)
```

**Golden Rules:**
- Communication flows **top-down only** — NO lateral messages
- All messages use `AgentMessage` Pydantic schema
- All events published through `EventBus` are HMAC-SHA256 signed
- Every agent has exactly one supervisor parent

---

## 1. Agent Archetypes (GeoSupply-specific)

### Coordinator Agent (Layer 3)
```python
# Role: Receives tasks from Supervisor, decomposes, dispatches to Workers
# Examples: SwarmManagerAgent, RouteManagerAgent
# Pattern: task → decompose → parallel dispatch → aggregate → return
class CoordinatorAgent(BaseAgent):
    tier = LLMTier.MEDIUM_14B
    capabilities = ["task_decompose", "result_aggregate"]
```

### Specialist Agent (Layer 3)
```python
# Role: Deep domain logic, single-purpose
# Examples: BudgetManagerAgent, TimelineGeneratorAgent
# Pattern: receive → validate → execute domain logic → return schema
class SpecialistAgent(BaseAgent):
    tier = LLMTier.SMALL_3B   # Most specialists use Tier 1 STATIC
    capabilities = ["single_domain_action"]
```

### Monitor Agent (Infrastructure, OFF DAG)
```python
# Role: Horizontal cross-cutting — never in critical path
# Examples: LoggingAgent, HealthCheckAgent, SecurityAgent
# Pattern: observe all → no blocking → fire-and-forget publish
class MonitorAgent(BaseAgent):
    tier = LLMTier.CPU_ONLY   # No LLM — pure computation
    on_critical_path = False   # MANDATORY for infra agents
```

### Security Agent (Layer 7 / LoopholeHunter)
```python
# Role: Continuous audit, pen tests, finding events
# Publishes LoopholeFinding schema on violations
class AuditAgent(BaseAgent):
    tier = LLMTier.LARGE_20B  # Needs reasoning for vuln analysis
    capabilities = ["pen_test", "schema_audit", "override_review"]
```

---

## 2. State Machine Design (G2 — LOCKED)

```python
# VALID state transitions — never allow arbitrary transitions
_VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE:     {AgentState.BUSY},
    AgentState.BUSY:     {AgentState.DONE, AgentState.ERROR},
    AgentState.DONE:     {AgentState.IDLE},
    AgentState.ERROR:    {AgentState.RECOVERY, AgentState.IDLE},
    AgentState.RECOVERY: {AgentState.IDLE, AgentState.ERROR},
}

async def _transition(self, new_state: AgentState) -> None:
    if new_state not in self._VALID_TRANSITIONS[self._state]:
        raise InvalidStateTransition(f"{self._state} → {new_state}")
    self._state = new_state
```

**Testing requirement**: Every agent test MUST verify invalid transitions raise `InvalidStateTransition`.

---

## 3. Communication Patterns

### Standard Task Dispatch
```python
# Supervisor → Agent (top-down only)
msg = AgentMessage(
    sender_id=supervisor.id,
    recipient_id=agent.id,
    payload=TaskPacket(action="analyze", data={...}),
    trace_id=trace_id,
)
await event_bus.publish(channel=f"agent.{agent.id}", message=msg)
```

### Result Aggregation
```python
# Agent → Supervisor (only permitted upward path)
result = AgentMessage(
    sender_id=agent.id,
    recipient_id=supervisor.id,
    payload={"result": output, "meta": {"cost_inr": 0.42}},
    trace_id=msg.trace_id,  # Preserve trace chain
)
```

### Infrastructure Events (Off-band)
```python
# LoggingAgent subscribes to ALL channels — never blocks
# HealthCheckAgent publishes to health.* — Supervisor reads async
# SecurityAgent publishes signing keys — never inline
```

---

## 4. MoE Gating (MoERouterAgent)

```python
# Expert selection algorithm:
# 1. Encode task capabilities required
# 2. Match against agent.capabilities registry
# 3. Score: capability_match * health_score * budget_headroom
# 4. Route to top-scoring available expert

ROUTING_WEIGHTS = {
    "capability_match": 0.50,
    "health_score":     0.30,
    "budget_headroom":  0.20,
}
```

---

## 5. Failure Handling

```python
# Every agent execute() must handle unknown actions:
async def execute(self, action: str, payload: dict) -> dict:
    handlers = {"analyze": self._analyze, "summarize": self._summarize}
    if action not in handlers:
        return {"error": f"Unknown action: {action}", "meta": {"cost_inr": 0.0}}
    return await handlers[action](payload)

# Circuit breaker for all Tier-3 calls:
@internal_breaker
async def _call_llm(self, prompt: str) -> str: ...
```

---

## 6. New Agent Checklist

- [ ] Inherits `BaseAgent`
- [ ] Defines `name`, `tier`, `capabilities`
- [ ] `_VALID_TRANSITIONS` map present
- [ ] `execute()` handles unknown actions gracefully
- [ ] `setup()` and `teardown()` implemented
- [ ] Infrastructure agents have `on_critical_path = False`
- [ ] All external calls use `@internal_breaker`
- [ ] All costs tracked as `cost_inr` in meta
- [ ] Unit test covers: happy path, invalid transition, unknown action, budget exhaustion
- [ ] Added to audit discovery via base class `__subclasses__()`

---

## Related Skills
- `swarm-orchestrator` — SwarmMaster task decomposition and DAG routing
- `supervisor-designer` — Supervisor budget gating and backpressure
- `worker-factory` — Layer 5 worker scaffolding
- `loophole-hunter` — Audit agent for security findings
