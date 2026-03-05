# Chapter 1: Executive Summary

## GeoSupply AI v9.0 — What Changed from v8.0

GeoSupply AI v9.0 is a **complete architectural improvisation** of the v8.0 India-centric geopolitical supply chain intelligence platform. While v8.0 introduced the 5-layer swarm with MoE routing and fixed critical RAG/hallucination bugs, v9.0 **re-engineers the agent hierarchy** with modern agentic patterns.

---

## v8.0 → v9.0 Improvement Matrix

| Area | v8.0 (Current) | v9.0 (Improvised) | Impact |
|------|----------------|-------------------|--------|
| **Layers** | 5 layers (L0-L5) | 7 layers with dedicated SubAgent + Supervisor | Cleaner separation of concerns |
| **Worker Pattern** | Ad-hoc worker classes | `BaseWorker` with lifecycle hooks, auto-instrumentation | 60% less boilerplate per worker |
| **SubAgent Pattern** | Implicit (inline code) | `BaseSubAgent` with DAG-based pipeline composition | Reusable multi-step workflows |
| **Agent Pattern** | Flat domain grouping | Capability-advertising agents with state machines | Dynamic routing, backpressure |
| **Supervisor** | Manager = Agent (same layer) | Dedicated `BaseSupervisor` layer with work-stealing | Priority scheduling, budget gates |
| **Orchestrator** | MoE gate as routing table | Full `SwarmMaster` with decomposition + dependency resolution | True hierarchical orchestration |
| **Static Methods** | STATIC decoder only | `@staticmethod` patterns for validation, cost, schema | Zero-allocation enforcement |
| **Observability** | LoggingAgent only | Distributed tracing + event bus + metrics export | Full request lineage |
| **Self-healing** | HealthCheck + manual | Automated circuit recovery, queue flush, process restart | Zero-touch recovery |
| **Error Handling** | Return error dict | Structured `Result[T]` monad with error propagation | Type-safe error chains |
| **Backpressure** | None (6 slot limit only) | Per-supervisor queue depth + rejection + spillover | Graceful overload handling |
| **Cost Tracking** | Per-agent INR logging | Per-span INR attribution with budget waterfall | INR cost per request path |

---

## v9.0 Design Goals

### 1. Hierarchy of Autonomy
```
Orchestrator  →  "WHAT needs to happen"     (decomposes, routes, budgets)
  Supervisor  →  "WHO should do it"          (schedules, prioritizes, gates)
    Agent     →  "HOW to coordinate it"      (manages workers, tracks state)
      SubAgent→  "HOW to pipeline steps"     (composes worker sequences)
        Worker→  "HOW to do one thing"       (executes, reports, retries)
```

### 2. Every Layer Has a Single Responsibility
- **Workers** execute a single task and return a result
- **SubAgents** compose multiple workers into a directed pipeline
- **Agents** own a domain and manage a pool of workers/subagents
- **Supervisors** enforce budgets, priorities, and phase gates
- **Orchestrator** decomposes user intent and routes to supervisors

### 3. Cost Is a First-Class Citizen
Every layer propagates INR cost upward:
```
Worker.process()    → returns cost_inr in meta
SubAgent.run()      → aggregates worker costs
Agent.execute()     → aggregates subagent costs
Supervisor.dispatch()→ enforces budget cap
Orchestrator.route() → global INR budget waterfall
```

### 4. Failure Is Expected, Recovery Is Automatic
```
Worker fails     → retry with backoff (max 3)
SubAgent fails   → skip step + log + continue pipeline
Agent fails      → circuit breaker opens → fallback agent
Supervisor fails → DEGRADED_MODE → core-only agents remain
Orchestrator fails → cold-start guard → minimal pipeline
```

---

## Hardware & Cost (Unchanged from v8.0)

```
PC RTX 5060 16GB     Mon-Thu 10am-6pm ONLY    Primary inference
Groq API             24/7 free 14,400 req/day  Primary fallback
GCP T4               INR 0 via Google Pro      Burst GPU
Claude API           Emergency only            INR 0.25/call
GitHub Actions       Free 2,000 min/month      Pipeline scheduler

TOTAL NEW SPEND:     INR 350/month
TOTAL INC GOOGLE PRO: INR 2,300/month
```

---

## Agent Census v9.0

| Layer | Count | Role |
|-------|-------|------|
| Layer 0 — Human Operator | 2 | Claude Chat + Antigravity |
| Layer 1 — Orchestrator | 1 | SwarmMaster (MoE + Decomposer + Budget) |
| Layer 2 — Supervisors | 10 | Domain manager orchestrators |
| Layer 3 — Agents | 15 | Domain agents (6 infra + 4 dev + 5 test) |
| Layer 4 — SubAgents | 8 | Composable pipeline agents |
| Layer 5 — Workers | 32 | Specialized execution agents |
| Layer 6 — Model Pool | 6 | LLM/ML model backends |
| **Total** | **74** | **Complete swarm** |
