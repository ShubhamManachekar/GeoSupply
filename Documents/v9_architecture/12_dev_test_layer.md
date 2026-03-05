# Chapter 12: Dev & Test Agent Layers

## Dev Agents (4 — Build-time only)

### DevSupervisor Workflow

```
1. DevSupervisor reads phase plan → assigns module to ScaffoldAgent
   Task brief: TASK, SPEC, INTERFACE, DEPENDS ON, SKILLS

2. ScaffoldAgent (with GitHub Copilot inline assist):
   → Reads AGENTS.md + module_interfaces.md
   → Reads relevant SKILL.md files
   → Reads 2 existing modules for style reference
   → Writes module + test file (Copilot helps with completions)
   → Runs pytest, fixes failures (max 3 attempts)

3. CodeReviewAgent (Claude Sonnet/Opus):
   → Logic correctness, interface compliance, security audit
   → ReviewReport: approved/rejected + issues
   → If rejected → back to ScaffoldAgent

4. DocGenAgent (Gemini Pro):
   → Docstrings, module README, CHANGELOG entry

5. RefactorAgent (post-phase):
   → Detects duplication, import inconsistency
   → isort + black formatting
   → Requires CodeReviewAgent approval for changes

6. DevSupervisor commits:
   → git add + commit with conventional message
   → Updates dependency graph
   → Unlocks next phase if complete
```

### Quality Gate (enforced by DevSupervisor)

```
[ ] pytest passes, coverage >80%
[ ] No hardcoded secrets (SecurityAgent.get_key() used)
[ ] All LLM calls via moe_gate.py
[ ] All API calls use @breaker
[ ] LoggingAgent.log() throughout
[ ] FactCheckAgent imported if LLM output generated
[ ] Type hints on all public functions
[ ] INR in all cost messages
[ ] STATIC decoder used if Tier-1 schema output
[ ] CyberDefenseAgent.scan_input() on all ingestion (NEW v9)
```

---

## Test Agents (5 — Build + Production)

| Agent | When | Coverage | Key Check |
|-------|------|----------|-----------|
| UnitTestAgent | Every commit | 80% min | 7 standard test categories |
| IntegrationTestAgent | Phase complete | 8 scenarios | End-to-end data flows |
| LoadTestAgent | Week 7 | SLA <12min | p50/p95/p99 latency |
| RegressionTestAgent | Every PR + weekly | Baseline F1 | No module degradation |
| ContractTestAgent | Phase + weekly | 100% schemas | All Pydantic contracts valid |

### 8 Integration Test Scenarios

```
1. Full pipeline:       news article in → IntelBrief out
2. Multilingual:        Hindi article → English brief
3. Fake news:           fabricated article → FAKE tag + quarantine
4. PC offline:          routing falls back to Groq → verified
5. India API chain:     ULIP → DGFT → port brief
6. RAG multi-hop:       complex query → multi-source brief
7. MoA synthesis:       3 proposers → aggregated brief
8. Cold-start:          empty DB → DEGRADED_MODE → graceful output
9. Cyber threat (NEW):  malicious input → injection detected → quarantined
```
