# GeoSupply AI — Final Architecture
## FA v1 (Final Architecture v1) | March 2026 | All Costs in INR | Classification: Confidential

> **"Every agent is a citizen, not a script. Trust nothing. Verify everything."**

---

## Architecture at a Glance

| Metric | Count |
|--------|-------|
| **Layers** | 7 + LoopholeHunter cross-layer |
| **Workers** | 40 |
| **SubAgents** | 13 |
| **Agents** | 38 |
| **Supervisors** | 14 |
| **APIs** | 42+ |
| **Skills** | 30 |
| **Pydantic Schemas** | 23 |
| **Continuous Audit Checks** | 24 |
| **Penetration Tests** | 8 |
| **Test Scenarios** | 18 |
| **Total Components** | ~137 |

---

## Document Index — 10 Parts

| Part | File | Title | Pages |
|------|------|-------|-------|
| I | [Part_I_Foundation.md](./Part_I_Foundation.md) | Foundation — Principles, Topology, Evolution | Core |
| II | [Part_II_Worker_Layer.md](./Part_II_Worker_Layer.md) | Worker Layer — BaseWorker + 40 Workers | Layer 5 |
| III | [Part_III_SubAgent_Layer.md](./Part_III_SubAgent_Layer.md) | SubAgent Layer — Pipelines + 13 SubAgents | Layer 4 |
| IV | [Part_IV_Agent_Layer.md](./Part_IV_Agent_Layer.md) | Agent Layer — 38 Agents + Capabilities | Layer 3 |
| V | [Part_V_Supervisor_Orchestrator.md](./Part_V_Supervisor_Orchestrator.md) | Supervisors (14) + SwarmMaster Orchestrator | Layers 1-2 |
| VI | [Part_VI_Intelligence_Engine.md](./Part_VI_Intelligence_Engine.md) | Self-Learning, Knowledge Graph, Cyber Threat Intel | Intelligence |
| VII | [Part_VII_Operations.md](./Part_VII_Operations.md) | Admin CLI, Portal, Autonomous Ops, DR, Cost | Operations |
| VIII | [Part_VIII_Security.md](./Part_VIII_Security.md) | Security Hardening, LoopholeHunter, PenTest | Security |
| IX | [Part_IX_Revenue_DevOps.md](./Part_IX_Revenue_DevOps.md) | Marketing, Revenue, Tech Team, CI/CD, Dev Tooling | Business |
| X | [Part_X_Registry_Roadmap.md](./Part_X_Registry_Roadmap.md) | APIs, Skills, Schemas, Census, Build Roadmap | Reference |

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

## FA v1 Gap Mitigations Applied

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
