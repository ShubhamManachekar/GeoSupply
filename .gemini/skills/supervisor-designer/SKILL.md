---
name: supervisor-designer
description: Layer 2 Supervisor design for GeoSupply — budget gating, priority scheduling, backpressure, health monitoring, and domain-specific supervisor implementations for all 14 supervisors in FA v3.
---

# Supervisor Designer — Layer 2 Domain Supervisors

> Custom GeoSupply skill — 14 supervisors bridging SwarmMaster and Agents

## Implementation Status (Session 21 | 2026-03-19)
| Supervisor | Domain | Budget | Status | Notes |
|------------|--------|--------|--------|-------|
| IngestionSupervisor | ingestion | ₹15/cycle | ✅ | |
| QualitySupervisor | quality | ₹10/cycle | ✅ | manages FactCheckAgent + SummarizationAuditAgent |
| NLPSupervisor | nlp | ₹8/cycle | ✅ | **+InputSanitiserWorker pre-gate in dispatch()** |
| IntelSupervisor | intel | ₹20/cycle | ✅ | |
| MLSupervisor | ml | ₹5/cycle | ⬜ | |
| IndiaSupervisor | india | ₹10/cycle | ⬜ | |
| DashboardSupervisor | dashboard | ₹3/cycle | ⬜ | |
| InfraSupervisor | infra | ₹2/cycle | ⬜ | subscribes to watchdog.alert for restart |
| DevSupervisor | dev | ₹5/cycle | ⬜ | |
| TestSupervisor | test | ₹5/cycle | ⬜ | |
| TechSupervisor | tech | ₹5/cycle | ⬜ | |
| MarketingSupervisor | marketing | ₹5/cycle | ⬜ | SummarizationAuditAgent must run before tweet publish |
| LoopholeHunterSupervisor | security | ₹1/cycle | ⬜ | |
| DisasterRecoverySupervisor | dr | ₹0/cycle | ⬜ | |

**NLPSupervisor pattern**: overrides `dispatch()` → calls `InputSanitiserWorker.process()` on `text` field → rejects injection; then `super().dispatch()`.
**IntelSupervisor pattern**: routes 6 agents + Tier-3 budget pre-check; `tier3_agents()` helper.
**InfraSupervisor (next)**: must subscribe to `watchdog.alert` topic and restart STUCK agents via `agent.safe_execute({"action": "recover"})`.

## Supervisor Responsibilities

```
Layer 2 sits between:
  SwarmMaster (Layer 1) ← receives TaskPacket
  Supervisor (Layer 2)  ← budget gate, priority sort, backpressure
  Agents (Layer 3)      ← dispatched individual tasks
```

**Each supervisor owns**:
1. Budget allocation for its domain
2. Priority queue for incoming tasks
3. Backpressure when agents are saturated
4. Health monitoring of its child agents

---

## 1. BaseSupervisor Pattern

```python
class BaseSupervisor:
    """
    Abstract supervisor base — all 14 supervisors inherit from this.
    Manages: budget, priority queue, backpressure, health checks.
    """
    name: str               # Override in subclass
    domain: str             # Override: "ingest", "nlp", "intel", etc.
    budget_cap_inr: float   # Domain budget from SwarmMaster allocation
    max_queue_depth: int = 100    # Backpressure threshold
    agents: list[BaseAgent] = []  # Child agents this supervisor manages

    async def submit(self, task: TaskPacket) -> str:
        """Submit task to domain queue. Returns task_id."""
        # 1. Budget gate
        if not await self._budget_gate(task):
            return await self._handle_budget_exhausted(task)

        # 2. Backpressure
        if self._queue.qsize() >= self.max_queue_depth:
            return await self._handle_backpressure(task)

        # 3. Priority sort and enqueue
        priority = self._calculate_priority(task)
        await self._queue.put((priority, task))
        return task.task_id

    async def _process_queue(self) -> None:
        """Main loop: dequeue → route to agent → collect result."""
        while True:
            priority, task = await self._queue.get()
            agent = await self._select_agent(task)
            if agent:
                asyncio.create_task(self._dispatch(agent, task))
            else:
                await self._handle_no_agent_available(task)

    def _calculate_priority(self, task: TaskPacket) -> int:
        """Lower number = higher priority."""
        PRIORITY_MAP = {
            "CRITICAL": 1,
            "HIGH":     2,
            "MEDIUM":   3,
            "LOW":      4,
        }
        return PRIORITY_MAP.get(task.priority, 3)
```

---

## 2. The 14 Supervisors

```python
# Domain supervisors (8)
class IngestSupervisor(BaseSupervisor):
    """Manages: NewsWorker, AISWorker, TelegramWorker, IndiaAPIWorker"""
    name = "ingest_supervisor"
    domain = "ingest"
    budget_cap_inr = 50.0   # External API costs

class NLPSupervisor(BaseSupervisor):
    """Manages: SentimentWorker, NERWorker, ClaimWorker, TranslationWorker"""
    name = "nlp_supervisor"
    domain = "nlp"
    budget_cap_inr = 20.0   # Local models — mostly free

class IntelSupervisor(BaseSupervisor):
    """Manages: KnowledgeGraphAgent, VerifierWorker, PropagandaWorker"""
    name = "intel_supervisor"
    domain = "intel"
    budget_cap_inr = 150.0  # Largest budget — Tier-3 verification

class MLSupervisor(BaseSupervisor):
    """Manages: ConflictWorker, RetrainWorker, DriftWorker"""
    name = "ml_supervisor"
    domain = "ml"
    budget_cap_inr = 0.0    # CPU_ONLY — no LLM costs

class IndiaSupervisor(BaseSupervisor):
    """Manages: IndiaIntelWorker, MonsoonWorker"""
    name = "india_supervisor"
    domain = "india"
    budget_cap_inr = 10.0

class DashboardSupervisor(BaseSupervisor):
    """Manages: StreamlitWorker, CIVisualisationWorker"""
    name = "dashboard_supervisor"
    domain = "dashboard"
    budget_cap_inr = 5.0

# Infrastructure supervisors (4)
class InfraSupervisor(BaseSupervisor):
    """Manages: LoggingAgent, HealthCheckAgent, SecurityAgent"""
    name = "infra_supervisor"
    domain = "infra"
    budget_cap_inr = 0.0    # Infrastructure — no LLM

class QualitySupervisor(BaseSupervisor):
    """Manages: FactCheckAgent, SemanticDriftSubAgent, HallucinationCheckSubAgent"""
    name = "quality_supervisor"
    domain = "quality"
    budget_cap_inr = 30.0

class DevSupervisor(BaseSupervisor):
    """Manages: ScaffoldAgent, CodeReviewAgent, DocGenAgent"""
    name = "dev_supervisor"
    domain = "dev"
    budget_cap_inr = 50.0

class MarketingSupervisor(BaseSupervisor):
    """Manages: ContentGenAgent, TwitterPublisher, PredictionAgent"""
    name = "marketing_supervisor"
    domain = "marketing"
    budget_cap_inr = 50.0

# Specialized supervisors (2 — v10 additions)
class LoopholeHunterSupervisor(BaseSupervisor):
    """Manages: LoopholeHunterAgent, PenTestAgent, OverrideAuditAgent"""
    name = "loophole_supervisor"
    domain = "security"
    budget_cap_inr = 30.0   # LoopholeHunter uses Tier-3

class DisasterRecoverySupervisor(BaseSupervisor):
    """Manages: BackupAgent, RestoreAgent"""
    name = "dr_supervisor"
    domain = "disaster_recovery"
    budget_cap_inr = 0.0
```

---

## 3. Budget Gating Logic

```python
async def _budget_gate(self, task: TaskPacket) -> bool:
    """Check domain budget before accepting task."""
    estimated_cost = self._estimate_task_cost(task)
    remaining = self.budget_cap_inr - self._spent_inr

    if estimated_cost > remaining:
        # Escalate to SwarmMaster for budget reallocation
        await self.event_bus.publish("supervisor.budget_request", AgentMessage(
            sender_id=self.id,
            payload={
                "domain": self.domain,
                "requested_inr": estimated_cost,
                "remaining_inr": remaining,
                "task_id": task.task_id,
            }
        ))
        return False
    return True
```

---

## 4. Backpressure Strategy

```python
# When queue depth exceeds max_queue_depth:
BACKPRESSURE_STRATEGIES = {
    "INGEST":   "drop_low_priority",    # Drop LOW priority tasks, keep CRITICAL/HIGH
    "NLP":      "delay_and_retry",      # Retry after 30 seconds
    "INTEL":    "escalate_to_master",   # Notify SwarmMaster to scale
    "ML":       "drop_and_log",         # ML can afford dropped tasks
    "INFRA":    "never_drop",           # Infrastructure never drops
}
```

---

## 5. Health Monitoring

```python
async def _health_check_children(self) -> dict:
    """Poll all child agents and report to SwarmMaster."""
    health = {}
    for agent in self.agents:
        status = await agent.execute("health", {})
        health[agent.name] = {
            "state":        agent.state.value,
            "last_seen":    status.get("last_seen"),
            "tasks_done":   status.get("tasks_done", 0),
            "error_count":  status.get("error_count", 0),
            "cost_inr":     status.get("total_cost_inr", 0.0),
        }
    return health
```

---

## 6. Supervisor Implementation Checklist

- [ ] Inherits `BaseSupervisor`
- [ ] `name`, `domain`, `budget_cap_inr` defined
- [ ] Priority queue uses `asyncio.PriorityQueue`
- [ ] `_budget_gate()` escalates (not silently drops) expensive tasks
- [ ] Backpressure strategy matched to domain type
- [ ] `_health_check_children()` runs every 60 seconds
- [ ] Test: submit 110 tasks → 100 accepted, 10 backpressured
- [ ] Test: budget exhausted → task escalated to SwarmMaster
- [ ] Test: CRITICAL priority task jumps LOW priority in queue
- [ ] Test: child agent ERROR state → supervisor routes to backup agent

---

## Related Skills
- `swarm-orchestrator` — SwarmMaster above supervisors
- `agent-designer` — Agents below supervisors
- `budget-controller` — Budget allocation logic
- `phase-gate-auditor` — Verify supervisor count matches FA v3 spec (14)
