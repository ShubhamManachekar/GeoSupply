# Chapter 6: Supervisor Layer — 10 Tier-Based Manager Orchestrators

## Design Philosophy

> **A Supervisor SCHEDULES, BUDGETS, and GATES. It never executes work directly.**

In v8, "Managers" were agents that both managed and sometimes executed. In v9, Supervisors are a **dedicated layer** that sits between the Orchestrator and Agents. They enforce priorities, budgets, phase gates, and backpressure.

---

## BaseSupervisor Abstract Class

```python
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from collections import deque
from enum import Enum
import asyncio

class Priority(Enum):
    P0_CRITICAL = 0   # RAG fix, hallucination, safety
    P1_HIGH = 1       # Source feedback, audit, CI propagation
    P2_MEDIUM = 2     # ChromaDB buffer, TTL, cold-start
    P3_LOW = 3        # Routing advisor, drift monitor, viz

class SupervisorState(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"     # Some agents unavailable
    BUDGET_EXCEEDED = "budget_exceeded"
    PHASE_BLOCKED = "phase_blocked"

class BudgetGate(BaseModel):
    """INR budget enforcement per supervisor."""
    hourly_limit_inr: float = 50.0
    daily_limit_inr: float = 300.0
    monthly_limit_inr: float = 500.0
    current_hour_inr: float = 0.0
    current_day_inr: float = 0.0
    current_month_inr: float = 0.0

    def can_spend(self, amount_inr: float) -> bool:
        return (
            self.current_hour_inr + amount_inr <= self.hourly_limit_inr
            and self.current_day_inr + amount_inr <= self.daily_limit_inr
            and self.current_month_inr + amount_inr <= self.monthly_limit_inr
        )

    def record_spend(self, amount_inr: float) -> None:
        self.current_hour_inr += amount_inr
        self.current_day_inr += amount_inr
        self.current_month_inr += amount_inr

class BaseSupervisor(ABC):
    """
    Tier-Based Manager Orchestrator.

    RESPONSIBILITIES:
        1. SCHEDULE:  Priority queue with work-stealing
        2. BUDGET:    INR caps per hour/day/month
        3. GATE:      Phase completion requirements
        4. HEALTH:    Route around unhealthy agents
        5. BACKPRESSURE: Reject when queue full, spill to fallback
        6. REPORT:    Aggregate cost + status upward to Orchestrator

    WORK-STEALING QUEUE:
        Tasks enter priority queue (P0 > P1 > P2 > P3)
        Available agents pull from queue (work-stealing)
        If agent pool exhausted → backpressure signal to Orchestrator
        If budget exceeded → DEGRADED_MODE, core-only tasks

    DOES NOT:
        - Execute tasks directly (delegates to Agents)
        - Route between domains (that's the Orchestrator)
        - Make LLM calls (that's the Worker)
    """

    name: str = "UnnamedSupervisor"
    domain: str = "unknown"
    max_queue_depth: int = 50

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = SupervisorState.ACTIVE
        self.budget = BudgetGate()
        self._task_queue: deque = deque()  # Priority-sorted
        self._agent_pool: dict[str, BaseAgent] = {}
        self._phase_complete: dict[int, bool] = {}

    # ─── Agent Pool ─────────────────────────────────
    def register_agent(self, agent: BaseAgent) -> None:
        self._agent_pool[agent.name] = agent

    def get_healthy_agents(self) -> list[BaseAgent]:
        return [a for a in self._agent_pool.values() if a.health_check()]

    # ─── Task Scheduling ────────────────────────────
    def enqueue(self, task: 'TaskPacket', priority: Priority) -> bool:
        """Add task to priority queue. Returns False if backpressure."""
        if len(self._task_queue) >= self.max_queue_depth:
            return False  # Backpressure signal

        if not self.budget.can_spend(task.estimated_cost_inr):
            self.state = SupervisorState.BUDGET_EXCEEDED
            return False

        # Insert sorted by priority
        self._task_queue.append((priority, task))
        self._task_queue = deque(sorted(self._task_queue, key=lambda x: x[0].value))
        return True

    async def dispatch(self) -> list['AgentReport']:
        """Work-stealing dispatch loop."""
        results = []
        available = self.get_healthy_agents()

        while self._task_queue and available:
            priority, task = self._task_queue.popleft()

            # Find best agent for this task
            agent = self._select_agent(task, available)
            if not agent:
                self._task_queue.appendleft((priority, task))  # Re-queue
                break

            if not agent.can_accept():
                continue  # Agent backpressure, try next

            report = await agent.execute(task)
            self.budget.record_spend(report.total_cost_inr)
            results.append(report)

        return results

    @abstractmethod
    def _select_agent(self, task: 'TaskPacket', available: list[BaseAgent]) -> Optional[BaseAgent]:
        """Domain-specific agent selection logic."""
        ...

    # ─── Phase Gating ───────────────────────────────
    def mark_phase_complete(self, phase: int) -> None:
        self._phase_complete[phase] = True

    def is_phase_complete(self, phase: int) -> bool:
        return self._phase_complete.get(phase, False)
```

---

## 10 Concrete Supervisors

### IngestSupervisor
```
Domain: Data ingestion
Agents: NewsWorker, IndiaAPIWorker, TelegramWorker, AISWorker
Cycle: Every 6 hours
Special: Circuit breaker coordination across all 4 ingestion sources
         Tracks source diversity metrics
         Triggers DEGRADED_MODE if >2 sources offline
```

### NLPSupervisor
```
Domain: Natural Language Processing
Agents: LangWorker, TranslationWorker, SentimentWorker, NERWorker, EmbedWorker
Special: Multilingual routing via MoE gate
         STATIC decoder enforcement on Sentiment + NER
         Language detection → translation → processing pipeline
```

### IntelSupervisor
```
Domain: Intelligence Analysis
Agents: ClaimWorker, VerifierWorker, SourceCredWorker, AuthorWorker,
        NetworkWorker, CIBWorker, PropagandaWorker
Special: MoA synthesis for all intelligence output
         STATIC decoder on Claim + SourceCred
         Heaviest Tier-3 usage — budget-critical
```

### MLSupervisor
```
Domain: Machine Learning
Agents: ConflictWorker, RetrainWorker, DriftWorker
Special: Weekly retraining schedule (Tue/Thu on PC)
         XGBoost CI propagation to GeoRiskScore
         Platt calibration monitoring
```

### IndiaSupervisor
```
Domain: India-specific intelligence
Agents: IndiaIntelWorker, MonsoonWorker + India API connectors
Special: NDA compliance enforcement
         ULIP rate limiting (129 APIs)
         IMD monsoon tracking
         INR-denominated cost tracking
```

### DashboardSupervisor
```
Domain: Streamlit dashboard
Agents: StreamlitWorker, CIVisualisationWorker
Special: 9 page routing
         CI range indicator rendering
         WebSocket real-time updates
```

### InfraSupervisor
```
Domain: Infrastructure singletons
Agents: LoggingAgent, FactCheckAgent, HealthCheckAgent,
        SecurityAgent, AuditorAgent, SourceFeedbackAgent
Special: Singleton lifecycle management
         Always-on — never enters DEGRADED_MODE
         Off critical DAG path
```

### QualitySupervisor
```
Domain: Quality assurance
Agents: FactCheckAgent pipeline, HallucinationCheckSubAgent
Special: Enforces HALLUCINATION_FLOOR = 0.70 globally
         >20% UNVERIFIED → reject entire brief
         Quarantine → SourceFeedbackSubAgent trigger
```

### DevSupervisor
```
Domain: Development (build-time only)
Agents: ScaffoldAgent, CodeReviewAgent, DocGenAgent, RefactorAgent
Special: Strict phase build order enforcement
         ScaffoldAgent → CodeReviewAgent → DocGenAgent pipeline
         80% coverage gate before phase advance
         Never runs in production
```

### TestSupervisor
```
Domain: Testing (build + production)
Agents: UnitTestAgent, IntegrationTestAgent, LoadTestAgent,
        RegressionTestAgent, ContractTestAgent
Special: Coverage tracking across all 45 modules
         Regression blocking on every PR
         Weekly Sunday full test suite
         Contract validation per phase
```
