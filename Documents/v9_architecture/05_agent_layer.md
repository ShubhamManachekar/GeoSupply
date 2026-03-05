# Chapter 5: Agent Layer — Domain Agents with Capability Advertising

## Design Philosophy

> **An Agent OWNS a domain. It manages workers, tracks state, and advertises what it can do.**

In v8, agents and managers were conflated. In v9, Agents are **capability-advertising executors** that own worker pools and coordinate sub-agents. They do NOT schedule or budget — that's the Supervisor's job.

---

## BaseAgent Abstract Class

```python
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from enum import Enum
import asyncio

class AgentState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"           # Waiting for worker results
    DEGRADED = "degraded"         # Some workers unavailable
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open" # All workers failed

class AgentCapability(BaseModel):
    """What this agent can do — used by MoE for routing."""
    task_types: set[str]          # e.g. {"NER", "SENTIMENT", "TRANSLATE"}
    max_concurrent: int           # Max parallel worker invocations
    tier: int                     # Primary model tier
    supports_static: bool         # Whether STATIC decoder is available
    domain: str                   # e.g. "nlp", "intel", "supply"

class AgentReport(BaseModel):
    """Standardized report from Agent to Supervisor."""
    status: str
    data: dict
    meta: dict
    workers_used: list[str]
    total_cost_inr: float
    total_latency_ms: float
    confidence: float             # Aggregated confidence score

class BaseAgent(ABC):
    """
    Base class for all domain agents.

    RESPONSIBILITIES:
        1. Declare capabilities via get_capabilities()
        2. Manage a pool of workers
        3. Execute tasks by dispatching to appropriate workers
        4. Track agent state (IDLE → PROCESSING → COMPLETE)
        5. Report results + cost to parent Supervisor
        6. Handle backpressure (reject when overloaded)

    STATE MACHINE:
        IDLE ──task──► PROCESSING ──workers──► WAITING ──results──► IDLE
                           │                                          │
                           ▼                                          ▼
                       ERROR ◄──circuit_open──── DEGRADED ◄──partial─┘

    DOES NOT:
        - Schedule tasks (that's the Supervisor)
        - Manage budgets (that's the Supervisor)
        - Route between domains (that's the Orchestrator)
    """

    name: str = "UnnamedAgent"
    domain: str = "unknown"

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = AgentState.IDLE
        self._worker_pool: dict[str, BaseWorker] = {}
        self._queue_depth = 0
        self._max_queue = 10

    # ─── Capability Protocol ────────────────────────
    @abstractmethod
    def get_capabilities(self) -> AgentCapability:
        """Declare what task types this agent handles."""
        ...

    # ─── Worker Pool Management ─────────────────────
    def register_worker(self, worker: 'BaseWorker') -> None:
        """Register a worker in this agent's pool."""
        self._worker_pool[worker.name] = worker
        worker.setup()

    def get_available_workers(self) -> list[str]:
        """Return names of workers that are healthy."""
        return [
            name for name, w in self._worker_pool.items()
            if w.health_check()
        ]

    # ─── Backpressure ───────────────────────────────
    def can_accept(self) -> bool:
        """Check if agent can accept more work."""
        return self._queue_depth < self._max_queue

    # ─── Execution ──────────────────────────────────
    @abstractmethod
    async def execute(self, task: 'TaskPacket') -> AgentReport:
        """Execute a task by dispatching to workers/subagents."""
        ...

    # ─── Health ─────────────────────────────────────
    def health_check(self) -> bool:
        healthy_workers = len(self.get_available_workers())
        total_workers = len(self._worker_pool)
        if healthy_workers == 0:
            self.state = AgentState.CIRCUIT_OPEN
            return False
        if healthy_workers < total_workers:
            self.state = AgentState.DEGRADED
        return True
```

---

## Singleton Pattern for Infrastructure Agents

```python
from functools import wraps

def singleton(cls):
    """Decorator that makes an Agent class a singleton."""
    instances = {}
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance

@singleton
class LoggingAgent(BaseAgent):
    """
    Singleton infrastructure agent. Imported by EVERY module.
    Never call print() — always LoggingAgent.log()

    Events logged:
        moe_gate, llm_call, module_process, api_call,
        agent_spawn, moa_trace, fact_check, source_penalty, cost_alert
    """
    name = "LoggingAgent"
    domain = "infrastructure"

    def get_capabilities(self) -> AgentCapability:
        return AgentCapability(
            task_types={"LOG_EVENT", "COST_REPORT", "ALERT"},
            max_concurrent=100,  # Non-blocking
            tier=0,
            supports_static=False,
            domain="infrastructure"
        )

    def log(self, event_type: str, **kwargs) -> None:
        """Universal logging endpoint. All agents call this."""
        record = {
            "event": event_type,
            "ts": time.time(),
            "session_id": kwargs.get("session_id", ""),
            "cost_inr": kwargs.get("cost_inr", 0.0),
            **kwargs
        }
        # Write to Supabase swarm_logs table
        # Push to Streamlit real-time dashboard
        ...

@singleton
class FactCheckAgent(BaseAgent):
    """
    7-step verification pipeline. HALLUCINATION_FLOOR = 0.70 (LOCKED).

    Steps:
        1. Source credibility
        2. Cross-reference (ChromaDB evidence)
        3. Claim extraction (isolate verifiable claims)
        4. Contradiction detection
        5. Temporal validity
        6. Propaganda pattern detection
        7. Confidence scoring → VERIFIED/DISPUTED/FAKE/UNVERIFIED

    Triggers SourceFeedbackSubAgent on every rejection.
    """
    name = "FactCheckAgent"
    domain = "infrastructure"
    HALLUCINATION_FLOOR = 0.70  # LOCKED — from config.py

    def get_capabilities(self) -> AgentCapability:
        return AgentCapability(
            task_types={"FACT_CHECK", "VERIFY_BATCH", "QUARANTINE"},
            max_concurrent=5,
            tier=3,
            supports_static=False,
            domain="infrastructure"
        )

    async def verify(self, claims: list[dict]) -> dict:
        """Run 7-step pipeline on claims."""
        unverified_ratio = 0.0
        results = []
        for claim in claims:
            score = await self._run_7_steps(claim)
            if score < self.HALLUCINATION_FLOOR:
                # Quarantine + trigger source feedback
                await SourceFeedbackSubAgent(self.session_id).run(claim)
            results.append({"claim": claim, "score": score})
            unverified_ratio = len([r for r in results if r["score"] < 0.70]) / len(results)

        if unverified_ratio > 0.20:
            return {"status": "rejected", "unverified_ratio": unverified_ratio}
        return {"status": "passed", "results": results}
```

---

## Complete Agent Inventory

### Infrastructure Agents (6 singletons — always on)

| Agent | Capabilities | Model | Key Feature |
|-------|-------------|-------|-------------|
| LoggingAgent | LOG_EVENT, COST_REPORT | None | Every event, INR cost, Supabase |
| FactCheckAgent | FACT_CHECK, VERIFY_BATCH | Tier 3 | 7-step, 0.70 floor, source feedback |
| HealthCheckAgent | HEALTH_POLL, ALERT | None | 28 APIs, INR thresholds, self-heal |
| SecurityAgent | GET_KEY, SANCTIONS_CHECK | None | Key rotation, OFAC, audit trail |
| AuditorAgent | AUDIT_SAMPLE, DRIFT_DETECT | Tier 2 | Stratified 100%/30%/10%, drift vector |
| SourceFeedbackAgent | SOURCE_PENALTY | Tier 1⚡ | -0.05 per quarantine, +0.02/week |

### Dev Agents (4 — build-time only)

| Agent | Capabilities | Model | Key Feature |
|-------|-------------|-------|-------------|
| ScaffoldAgent | CODE_SCAFFOLD | Gemini Pro/Claude | Production-ready module files |
| CodeReviewAgent | CODE_REVIEW | Claude Sonnet/Opus | Logic + interface + security review |
| DocGenAgent | DOC_GENERATE | Gemini Pro | Docstrings + CHANGELOG |
| RefactorAgent | CODE_REFACTOR | Gemini Pro/Claude | Duplication, isort, black |

### Test Agents (5 — build + production)

| Agent | Capabilities | Runs When | Key Feature |
|-------|-------------|-----------|-------------|
| UnitTestAgent | UNIT_TEST | Every commit | 80% coverage gate |
| IntegrationTestAgent | INTEGRATION_TEST | Phase complete | 8 end-to-end scenarios |
| LoadTestAgent | LOAD_TEST | Week 7 | <12 min SLA, p50/p95/p99 |
| RegressionTestAgent | REGRESSION_TEST | Every PR + weekly | Baseline F1 comparison |
| ContractTestAgent | CONTRACT_TEST | Phase + weekly | Schema validation |
