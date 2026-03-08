# GeoSupply AI — Final Architecture
## FA v2 (Final Architecture v2) | March 2026 | All Costs in INR | Classification: Confidential

> Legacy Notice: `final_architecture/` is FA v2 reference material. For current implementation-truth and active planning, use `Documents/fa_v3_architecture/`.

> **FA v2 UPGRADE**: Integrated World Monitor reference features — natural disasters, aviation/military tracking, energy intelligence, financial signals, geographic convergence detection, and infrastructure cascade analysis. All new APIs are free tier.

> **"Every agent is a citizen, not a script. Trust nothing. Verify everything."**

---

## Architecture at a Glance

| Metric | FA v1 | FA v2 |
|--------|-------|-------|
| **Layers** | 7 + LH | 7 + LH |
| **Workers** | 41 | **45** (+4) |
| **SubAgents** | 13 | **15** (+2) |
| **Agents** | 39 | 39 |
| **Supervisors** | 14 | 14 |
| **APIs** | 42+ | **59+** (+17) |
| **Skills** | 31 | **33** (+2) |
| **Pydantic Schemas** | 25 | **28** (+3) |
| **Continuous Audit Checks** | 24 | 24 |
| **Penetration Tests** | 8 | 8 |
| **Test Scenarios** | 18 | 18 |
| **Total Components** | ~141 | **~147** |

---

## Document Index — 10 Parts

| Part | File | Title | Pages |
|------|------|-------|-------|
| I | [Part_I_Foundation.md](./Part_I_Foundation.md) | Foundation — Principles, Topology, Evolution | Core |
| II | [Part_II_Worker_Layer.md](./Part_II_Worker_Layer.md) | Worker Layer — BaseWorker + 45 Workers | Layer 5 |
| III | [Part_III_SubAgent_Layer.md](./Part_III_SubAgent_Layer.md) | SubAgent Layer — Pipelines + 15 SubAgents | Layer 4 |
| IV | [Part_IV_Agent_Layer.md](./Part_IV_Agent_Layer.md) | Agent Layer — 38 Agents + Capabilities | Layer 3 |
| V | [Part_V_Supervisor_Orchestrator.md](./Part_V_Supervisor_Orchestrator.md) | Supervisors (14) + SwarmMaster Orchestrator | Layers 1-2 |
| VI | [Part_VI_Intelligence_Engine.md](./Part_VI_Intelligence_Engine.md) | Self-Learning, Knowledge Graph, Cyber Threat Intel | Intelligence |
| VII | [Part_VII_Operations.md](./Part_VII_Operations.md) | Admin CLI, Portal, Autonomous Ops, DR, Cost | Operations |
| VIII | [Part_VIII_Security.md](./Part_VIII_Security.md) | Security Hardening, LoopholeHunter, PenTest | Security |
| IX | [Part_IX_Revenue_DevOps.md](./Part_IX_Revenue_DevOps.md) | Marketing, Revenue, Tech Team, CI/CD, Dev Tooling | Business |
| X | [Part_X_Registry_Roadmap.md](./Part_X_Registry_Roadmap.md) | APIs, Skills, Schemas, Census, Build Roadmap | Reference |
| XI | [Part_XI_API_Reference.md](./Part_XI_API_Reference.md) | API Implementation Reference — Endpoints, Auth, Rate Limits | Reference |

---

## Locked Principles (Never Override)

```
1. DAG + strict Pydantic typing across all tiers
2. Three-tier LLM routing: Tier 1 (3b) → Tier 2 (14b) → Tier 3 (20b)
3. No lateral Manager-to-Manager or Worker-to-Worker communication
4. Single-writer authority for Tier 0 over state persistence
5. Infrastructure agents OFF the critical DAG path
6. XGBoost + Platt scaling ISOLATED from LLMs
7. HALLUCINATION_FLOOR = 0.70 (LOCKED — from config.py)
8. All costs in INR — never USD
9. TRUST NOTHING — every data flow has a validator
10. Every agent has a watchdog; every override has an auditor
```

## Cross-Reference Verification

```
After writing each Part, the following cross-checks are performed:
  ✓ Every agent named in census exists in its layer chapter
  ✓ Every worker listed uses BaseWorker lifecycle
  ✓ Every STATIC worker listed in MoE routing table
  ✓ Every supervisor manages the agents claimed
  ✓ Every loophole fix has a LoopholeHunter check ID
  ✓ Every API listed has cost in INR
  ✓ Every skill is referenced by at least one agent
  ✓ No feature from v9 or v10 is omitted
```

## FA v1 Gap Mitigations Applied (Carried Forward into FA v2)

| Gap | Mitigation | Part Updated |
|-----|------------|-------------|
| G1 | BaseSubAgent setup()/teardown() lifecycle hooks | Part III |
| G2 | BaseAgent state transition guards (_VALID_TRANSITIONS) | Part IV |
| G3 | EventBus HMAC-SHA256 signing key management + 30-day rotation | Part VIII |
| G4 | SchemaVersionManager spec (versioning + migration strategy) | Part V |
| G5 | KG dedup key = (entity_source, entity_target, relation_type) | Part VI |
| G6 | Channel fingerprint baseline protocol (100-msg, KL thresholds) | Part VI |
| G7 | WebSocket JWT claims/scope/revocation spec | Part VII |
| G8 | MoA Level 2 weighted scoring formula | Part III |
| G9 | WorkerError Pydantic schema (schema #23) | Part II, X |
| G10 | Test fixture factory pattern strategy | Part VII, IX |
