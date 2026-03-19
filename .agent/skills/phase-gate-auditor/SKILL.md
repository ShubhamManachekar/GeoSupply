---
name: phase-gate-auditor
description: Phase gate audit procedures for GeoSupply — connectivity checks, logic gap validation, coverage verification, schema sync, DEVELOPMENT_TRAIL.md update, and security pen-test before closing any development phase.
---

# Phase Gate Auditor — GeoSupply Phase Closure Protocol

> Custom GeoSupply skill — run BEFORE closing any development phase

## Current Phase Status (2026-03-19 Session 20)
| Phase | Status | Tests | Notes |
|-------|--------|-------|-------|
| 0 | ✅ COMPLETE | — | config, schemas, base classes |
| 1 | ✅ COMPLETE | — | infra agents |
| 2 | ✅ COMPLETE | — | 4 ingestion workers |
| 3 | ✅ COMPLETE | — | 5 NLP workers |
| 4 | ✅ COMPLETE | 596 pass | 8/8 intel workers (Verifier+Author added) |
| 5 | ✅ COMPLETE | 596 pass | 5/5 subagents (RAGPipelineSubAgent added) |
| 6 | 🟡 PARTIAL | 596 pass | 4/14 supervisors (NLP+Intel added) |
| 7 | 🟡 PARTIAL | 596 pass | KGAgent in-memory; NetworkX/ChromaDB planned |
| 14 | ✅ COMPLETE | — | audit tooling |

## The Golden Rule

**NEVER close a phase without running this protocol.**
A failed audit after delivery costs 10x more than catching it here.

---

## Phase Gate Checklist (Run in Order)

### Step 1: Connectivity Check
```bash
# Verify all imports resolve — no circular deps, no missing modules
PYTHONPATH=src python -c "
import geosupply.workers
import geosupply.agents
import geosupply.core
import geosupply.schemas
import geosupply.config
print('✅ All imports resolved')
"
```

Expected: No ImportError, no circular dependency warnings.

---

### Step 2: Dynamic Audit (Strict Mode)
```bash
PYTHONPATH=src python -m geosupply.cli.audit --level strict
```

This checks:
- All BaseWorker subclasses override `process()`
- All BaseAgent subclasses have `_VALID_TRANSITIONS`
- Schema counts in `ALL_SCHEMAS` match `SCHEMA_VERSIONS`
- No orphaned test files (test exists but class doesn't)
- No undiscovered workers/agents (every class is importable)
- Logic breakage: MRO validation for all base class hierarchies

Expected exit code: `0`. Any non-zero = phase BLOCKED.

---

### Step 3: Full Test Suite
```bash
PYTHONPATH=src python -m pytest tests/unit/ \
  --cov=src/geosupply \
  --cov-report=term-missing \
  --cov-fail-under=80 \
  -W error::DeprecationWarning \
  -v
```

Expected:
- All tests PASS
- Coverage ≥ 80% (target 85%+)
- Zero DeprecationWarning (especially no `datetime.utcnow()`)

---

### Step 4: Security Audit (Pre-Gate)
```bash
# PT-01: Scan for hardcoded secrets
PYTHONPATH=src python -c "
import re, pathlib
PATTERNS = [r'sk-[a-zA-Z0-9]{32,}', r'api_key\s*=\s*[\"\\'][^\"\\'][10,}']
for f in pathlib.Path('src').rglob('*.py'):
    content = f.read_text()
    for p in PATTERNS:
        if re.search(p, content):
            print(f'❌ CRITICAL: Secret in {f}')
            exit(1)
print('✅ No hardcoded secrets found')
"

# PT-05: Verify HALLUCINATION_FLOOR is unchanged
PYTHONPATH=src python -c "
from geosupply.config import HALLUCINATION_FLOOR
assert HALLUCINATION_FLOOR == 0.70, f'CRITICAL: Floor changed to {HALLUCINATION_FLOOR}'
print(f'✅ HALLUCINATION_FLOOR = {HALLUCINATION_FLOOR}')
"

# PT-04: Verify BUDGET_CAP_INR is unchanged
PYTHONPATH=src python -c "
from geosupply.config import BUDGET_CAP_INR
assert BUDGET_CAP_INR == 500.0, f'CRITICAL: Budget cap changed to {BUDGET_CAP_INR}'
print(f'✅ BUDGET_CAP_INR = ₹{BUDGET_CAP_INR}')
"
```

---

### Step 5: Schema Sync Verification
```bash
PYTHONPATH=src python -c "
from geosupply.config import ALL_SCHEMAS, SCHEMA_VERSIONS
missing = [s.__name__ for s in ALL_SCHEMAS if s.__name__ not in SCHEMA_VERSIONS]
if missing:
    print(f'❌ Schemas missing from SCHEMA_VERSIONS: {missing}')
    exit(1)
print(f'✅ All {len(ALL_SCHEMAS)} schemas have version entries')
"
```

---

### Step 6: DEVELOPMENT_TRAIL.md Sync
Manually verify the following match audit output:
```markdown
## Sync Checklist
- [ ] Worker count in DEVELOPMENT_TRAIL.md matches `audit --level strict` output
- [ ] Agent count in DEVELOPMENT_TRAIL.md matches `audit --level strict` output
- [ ] All workers claimed as "completed" have test files in tests/unit/
- [ ] All agents claimed as "completed" have test files in tests/unit/
- [ ] Phase description accurately reflects implemented features
- [ ] "Next phase" section updated with correct remaining work
- [ ] Commit hash of phase gate noted in DEVELOPMENT_TRAIL.md
```

Update DEVELOPMENT_TRAIL.md with actual counts BEFORE committing phase gate.

---

### Step 7: Cost Model Verification
```bash
PYTHONPATH=src python -c "
from geosupply.config import (
    COST_ALERT_WARN_DAILY_INR, COST_ALERT_CRITICAL_DAILY_INR, BUDGET_CAP_INR
)
assert COST_ALERT_WARN_DAILY_INR < COST_ALERT_CRITICAL_DAILY_INR <= BUDGET_CAP_INR
print(f'✅ Cost thresholds: warn=₹{COST_ALERT_WARN_DAILY_INR}, critical=₹{COST_ALERT_CRITICAL_DAILY_INR}, cap=₹{BUDGET_CAP_INR}')
"
```

---

### Step 8: Git State Check
```bash
# Ensure no uncommitted changes before gate commit
git status --short
git diff --stat

# Verify branch is correct
git branch --show-current
# Expected: claude/analyze-codebase-architecture-LUkkc
```

---

## Phase-Specific Gates

### After Phase 2 (Ingestion Workers)
- [ ] NewsWorker, AISWorker, TelegramWorker, IndiaAPIWorker all pass tests
- [ ] External API calls all use `@breaker` decorator
- [ ] No API keys in source code (PT-01 passes)
- [ ] Rate limiting verified for each external API

### After Phase 3 (NLP Workers)
- [ ] SentimentWorker, NERWorker, ClaimWorker use `use_static = True`
- [ ] TranslationWorker handles all `INDIA_LANGUAGES` without error
- [ ] All Tier-1 workers return STATIC decoder outputs (not LLM text)

### After Phase 4 (Knowledge Graph)
- [ ] KG write buffer batch size = 50 (config verified)
- [ ] Dedup window = 3600 seconds (config verified)
- [ ] Only KnowledgeGraphAgent writes to KG (single-writer verified)

### After Phase 5 (SubAgents)
- [ ] All 13 SubAgents discoverable by audit
- [ ] RAG faithfulness score ≥ 0.70 on test queries
- [ ] GraphRAG traversal returns correct k-hop neighbors

### After Phase 6 (Supervisors)
- [ ] All 14 supervisors discoverable by audit
- [ ] Budget gating verified for each supervisor
- [ ] Backpressure tested at max_queue_depth

### After Phase 7 (SwarmMaster)
- [ ] DAG deadlock detection tested
- [ ] Degraded mode activation tested (budget, health, SLA)
- [ ] Full end-to-end pipeline: Layer 0 → SwarmMaster → ... → GeoRiskScore

---

## Gate Failure Responses

| Failure | Action |
|---------|--------|
| Import error | Fix circular dep or missing module BEFORE proceeding |
| Test failure | Fix test or implementation — NEVER mock to make it pass |
| Coverage < 80% | Add tests for uncovered lines |
| Hardcoded secret | Remove immediately, rotate key, add to .gitignore |
| HALLUCINATION_FLOOR changed | Revert immediately — this is LOCKED |
| DEVELOPMENT_TRAIL out of sync | Update trail first, then gate |
| Schema missing version entry | Add to SCHEMA_VERSIONS before gate |

---

## Gate Commit Message Format

```
feat(phase{N}): {description} — gate passed

Audit results:
- Workers: {N} implemented ({M} total target)
- Agents: {N} implemented ({M} total target)
- Test coverage: {N}%
- Security: PT-01 through PT-08 all pass
- Schemas: {N} schemas, all versioned

DEVELOPMENT_TRAIL.md updated.
```

---

## Related Skills
- `self-improving-agent` — si:sync-trail updates DEVELOPMENT_TRAIL.md
- `security-auditor` — Security pen tests run at gate
- `loophole-hunter` — LoopholeFinding scan before gate
- `geosupply-dev` — Rules enforced at gate
