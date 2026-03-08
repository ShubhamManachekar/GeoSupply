# GeoSupply AI v9.0 — Improvised Modern Agentic Architecture

**Version:** 9.0 | **Date:** March 2026 | **Classification:** Confidential  
**Evolved from:** v8.0 Architecture | **All costs in INR**

> Legacy Notice: `v9_architecture/` is historical context. Use `Documents/fa_v3_architecture/` as the canonical architecture set.

---

## Document Index

| Chapter | File | Topic |
|---------|------|-------|
| 01 | [01_executive_summary.md](./01_executive_summary.md) | Executive Summary & What Changed v8→v9 |
| 02 | [02_swarm_topology.md](./02_swarm_topology.md) | Complete 7-Layer Swarm Topology |
| 03 | [03_worker_layer.md](./03_worker_layer.md) | Worker Layer — BaseWorker + 32 Specialists |
| 04 | [04_subagent_layer.md](./04_subagent_layer.md) | Sub-Agent Layer — Composable Pipelines |
| 05 | [05_agent_layer.md](./05_agent_layer.md) | Agent Layer — Domain Agents + MoE |
| 06 | [06_supervisor_layer.md](./06_supervisor_layer.md) | Supervisor Layer — 10 Tier-Based Managers |
| 07 | [07_orchestrator_layer.md](./07_orchestrator_layer.md) | Orchestrator — SwarmMaster + MoE Gateway |
| 08 | [08_static_methods.md](./08_static_methods.md) | STATIC Decoder & Static Method Patterns |
| 09 | [09_modern_patterns.md](./09_modern_patterns.md) | Modern Agentic Patterns (Event Bus, Observability, Self-Healing) |
| 10 | [10_schemas_contracts.md](./10_schemas_contracts.md) | Pydantic Schemas & Message Contracts |
| 11 | [11_infrastructure.md](./11_infrastructure.md) | Infrastructure Agents (6 Singletons) |
| 12 | [12_dev_test_layer.md](./12_dev_test_layer.md) | Dev & Test Agent Layers |
| 13 | [13_build_roadmap.md](./13_build_roadmap.md) | Phase Build Order & Roadmap |
| 14 | [14_self_learning_intelligence.md](./14_self_learning_intelligence.md) | Self-Learning Intelligence Engine |
| 15 | [15_admin_cli_portal.md](./15_admin_cli_portal.md) | Admin CLI Manager & Web Portal |
| 16 | [16_autonomous_operations.md](./16_autonomous_operations.md) | Autonomous Operations + Manual Override |
| 17 | [17_dev_tooling.md](./17_dev_tooling.md) | Development Tooling (Copilot, Antigravity, Claude) |
| 18 | [18_cyber_security.md](./18_cyber_security.md) | Cyber Attack Tracking, Threat Intelligence & Security Hardening |
| 19 | [19_tech_team_cicd.md](./19_tech_team_cicd.md) | Tech Team Agents — CI/CD, API Discovery, Staging & Deployment |
| 20 | [20_marketing_agent.md](./20_marketing_agent.md) | Marketing & Revenue Agent — Twitter, Predictions, Monetisation |
| 21 | [21_v10_audit.md](./21_v10_audit.md) | v10 Architecture Audit — Loopholes, Logic Gaps, APIs & Skills |

---

## Architecture Philosophy (v9.0)

> **Every agent is a citizen, not a script.**  
> Workers have lifecycles. SubAgents compose pipelines. Agents advertise capabilities.  
> Supervisors enforce budgets. The Orchestrator orchestrates — never executes.

### Core Principles
1. **Hierarchy of Responsibility** — Worker < SubAgent < Agent < Supervisor < Orchestrator
2. **Capability-Based Routing** — Agents declare what they can do; MoE routes to them
3. **Static Enforcement** — Schema validity is a compile-time guarantee, not a runtime hope
4. **INR-First Economics** — Every layer tracks cost in INR; budget overflows trigger degradation
5. **Self-Healing by Default** — Every failure path has an automated recovery
6. **Observe Everything** — Distributed tracing from Orchestrator to Worker, per-step INR attribution
