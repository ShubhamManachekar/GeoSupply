---
name: self-improving-agent
description: Auto-memory curation for GeoSupply development sessions. Promotes proven patterns from session learnings into enforced project rules, skills, and CLAUDE.md. Prevents architecture drift across AI handoffs.
---

# Self-Improving Agent — GeoSupply Memory Curation

> Upstream source: alirezarezvani/claude-skills · engineering-team/self-improving-agent
> Adapted for: GeoSupply FA v3 AI handoff protocol, DEVELOPMENT_TRAIL.md, architecture drift prevention

## Core Commands

| Command | Action |
|---------|--------|
| `/si:review` | Scan MEMORY.md + DEVELOPMENT_TRAIL.md for promotion candidates |
| `/si:promote` | Graduate patterns to CLAUDE.md or `.agent/skills/geosupply-dev/SKILL.md` |
| `/si:extract` | Convert proven fix into a new standalone skill |
| `/si:status` | Show memory health: staleness, drift risk, coverage |
| `/si:remember` | Explicitly save a hard-won lesson |
| `/si:sync-trail` | Sync DEVELOPMENT_TRAIL.md with actual implemented state |

---

## Memory Architecture (3-Tier)

```
Tier 1: CLAUDE.md               ← Project rules (full load, highest priority)
Tier 2: DEVELOPMENT_TRAIL.md    ← AI handoff source-of-truth (first 200 lines)
Tier 3: .agent/skills/*/SKILL.md ← Domain-specific rules (load on demand)
```

**Promotion path**: session learning → `/si:review` → `/si:promote` → CLAUDE.md or skill file

---

## What to Promote

### Promote to CLAUDE.md (global enforcement)
- Any pattern that caused a build failure more than once
- Any architecture violation caught in audit
- Any banned Python pattern discovered in code review
- Any schema versioning rule learned from a breakage

### Promote to geosupply-dev/SKILL.md (developer guidance)
- New module creation patterns
- Test fixture improvements
- Audit CLI procedure refinements

### Extract as New Skill
- If a domain pattern is > 200 lines in MEMORY.md → extract to new skill file
- Example: GraphRAG patterns → `knowledge-graph/SKILL.md`

---

## GeoSupply-Specific Promotion Candidates

Track these recurring patterns for promotion:

```markdown
## CANDIDATE PATTERNS TO WATCH

### C1: datetime.utcnow() violations
- Seen: 3x in Phase 0, 1x in Phase 1
- Status: PROMOTED → geosupply-dev/SKILL.md (Banned Patterns)
- Rule: Use datetime.now(timezone.utc) ALWAYS

### C2: schema_version missing from new schemas
- Seen: 2x in Phase 1
- Status: PROMOTED → CLAUDE.md
- Rule: Every Pydantic schema MUST have schema_version: int = 1

### C3: cost_inr missing from meta dict
- Seen: 4x across phases
- Status: PROMOTE → Module Creation Checklist item
- Rule: Every process()/execute()/run() MUST return meta.cost_inr

### C4: Worker not registered in audit discovery
- Seen: 2x in Phase 2
- Status: PROMOTE → audit procedure
- Rule: Never hardcode component counts; use __subclasses__() discovery
```

---

## Development Trail Sync Protocol

Before any AI handoff, run `/si:sync-trail`:

```markdown
## SYNC CHECKLIST
1. [ ] Count actual implemented workers: python -m geosupply.cli.audit --level strict
2. [ ] Update DEVELOPMENT_TRAIL.md worker count to match audit output
3. [ ] Update DEVELOPMENT_TRAIL.md agent count to match audit output
4. [ ] Verify all claimed "completed" phases actually pass pytest
5. [ ] Flag any DEVELOPMENT_TRAIL.md claims that don't match code
6. [ ] Archive stale memory entries > 30 days old
```

**Why this matters**: GeoSupply DEVELOPMENT_TRAIL.md is the AI handoff document. Stale counts or false claims in it cause new AI sessions to build on wrong assumptions → architecture drift → wasted implementation.

---

## Anti-Drift Triggers

Automatically flag for review when:
- A new AI session finds component counts don't match DEVELOPMENT_TRAIL.md
- A test passes in DEVELOPMENT_TRAIL.md but fails in pytest
- A "completed" feature has no corresponding test file
- Any LOCKED constant (HALLUCINATION_FLOOR, BUDGET_CAP_INR) appears in a diff

---

## Memory Health Metrics

```
Freshness: % of entries < 14 days old     → target > 70%
Accuracy:  % claims verified by audit CLI  → target 100%
Coverage:  % phases with trail entries     → target 100%
Drift Risk: days since last sync-trail     → alert if > 7 days
```

---

## Related Skills
- `phase-gate-auditor` — Formal phase gate procedures that feed si:sync-trail
- `geosupply-dev` — Core development rules maintained by self-improving-agent
- `developers` — Rules enforced by this skill's promotions
