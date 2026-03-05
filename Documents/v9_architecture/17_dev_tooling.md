# Chapter 17: Development Tooling — Copilot, Antigravity, Claude

## Design Philosophy

> **Three AI assistants, each with clear roles. No overlap. No confusion.**

---

## Development Toolchain

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT WORKFLOW v9.0                     │
│                                                                  │
│  PLANNING & ARCHITECTURE                                        │
│  ┌─────────────────┐                                            │
│  │  Claude Chat     │  Architecture review, logic grading,      │
│  │  (Chat sessions) │  hallucination checking, INR cost analysis │
│  └────────┬────────┘                                            │
│           │ Design decisions + interface contracts               │
│           ▼                                                      │
│  BUILD & IMPLEMENTATION                                          │
│  ┌─────────────────┐  ┌──────────────────┐                     │
│  │  Antigravity     │  │  GitHub Copilot   │                     │
│  │  (Agent IDE)     │  │  (Inline assist)  │                     │
│  │                  │  │                   │                     │
│  │  Module scaffold │  │  Line completion  │                     │
│  │  Test generation │  │  Function bodies  │                     │
│  │  Git management  │  │  Docstrings       │                     │
│  │  Multi-file edits│  │  Quick fixes      │                     │
│  │  Browser testing │  │  Pattern suggest  │                     │
│  │  Skill execution │  │  Inline chat      │                     │
│  └────────┬────────┘  └────────┬─────────┘                     │
│           │                     │                                │
│           ▼                     ▼                                │
│  REVIEW & QUALITY                                               │
│  ┌─────────────────┐                                            │
│  │  Claude (Review)  │  Logic correctness, security audit,      │
│  │  + Antigravity    │  interface compliance, hallucination chk │
│  └─────────────────┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## GitHub Copilot Integration

### Copilot Role: Inline Development Assistant

```
COPILOT DOES:
    ✅ Line-by-line code completion in VS Code
    ✅ Function body generation from docstrings
    ✅ Test case suggestions from function signatures
    ✅ Quick inline fixes for type errors, imports
    ✅ Pattern matching from existing codebase
    ✅ Docstring generation for public functions
    ✅ Copilot Chat for quick questions about code

COPILOT DOES NOT:
    ❌ Module-level architecture decisions (Claude's job)
    ❌ Multi-file scaffolding (Antigravity's job)
    ❌ Git operations (Antigravity's job)
    ❌ Test execution + coverage tracking (Antigravity's job)
    ❌ Interface contract validation (Claude's job)
    ❌ Cross-module dependency analysis (Claude's job)

COPILOT CONTEXT FILES:
    .github/copilot-instructions.md — project-specific instructions
    Contains:
        - "All costs in INR, never USD"
        - "Use moe_gate.py for all LLM calls"
        - "Use @breaker for all API calls"
        - "Use LoggingAgent.log(), never print()"
        - "All public functions need type hints"
        - "Follow BaseWorker/BaseAgent/BaseSupervisor patterns"
```

### Copilot Instructions File

```markdown
# .github/copilot-instructions.md

## GeoSupply AI Project Rules for Copilot

### Mandatory Patterns
- All costs must be in INR (Indian Rupees), never USD
- Use `moe_gate.call()` for ALL LLM inference calls
- Use `@breaker` decorator for ALL external API calls
- Use `LoggingAgent.log()` for logging, never `print()`
- Use `SecurityAgent.get_key()` for API keys, never `os.getenv()`
- All public functions must have type hints and docstrings
- Worker classes must extend `BaseWorker`
- Agent classes must extend `BaseAgent`
- Return error dicts, never raise exceptions to callers

### Schema Rules
- All inter-agent messages use the standard message contract
- GeoRiskScore must include ci_low, ci_high, data_density
- HALLUCINATION_FLOOR = 0.70 (never override)
- STATIC decoder for Tier-1 schema-strict outputs

### Test Rules
- Every module needs a corresponding test file
- Minimum 80% coverage per module
- Mock all external APIs — tests must run offline
- Standard test categories: HappyPath, EmptyInput, MalformedInput,
  CircuitBreaker, HealthCheck, MessageContract, CostInINR
```

---

## Antigravity Integration

### Antigravity Role: Agent IDE & Orchestrator

```
ANTIGRAVITY DOES:
    ✅ Multi-file module scaffolding (ScaffoldAgent equivalent)
    ✅ Full test suite generation + execution
    ✅ Git operations (branch, commit, push, PR)
    ✅ Cross-file refactoring
    ✅ Browser testing (Streamlit dashboard verification)
    ✅ Skill-based development (reads SKILL.md files)
    ✅ Parallel worker agent spawning (6 max)
    ✅ Code review automation
    ✅ Pipeline execution + debugging

ANTIGRAVITY WORKFLOW PER MODULE:
    1. Read AGENTS.md + module_interfaces.md
    2. Read relevant SKILL.md files
    3. Read 2 existing modules for style reference
    4. Generate module + test file (with Copilot inline assist)
    5. Run pytest → fix failures (max 3 attempts)
    6. Commit with conventional message
    7. Update dependency graph
```

### GEMINI.md (Updated for v9 + Copilot)

```
# GEMINI.md — Antigravity Manager Agent v9.0

## Development Stack
Primary IDE assistant: GitHub Copilot (inline completion)
Module orchestrator:   Google Antigravity (multi-file, tests, git)
Architecture reviewer: Claude Chat (logic, interfaces, security)

## Task Brief Template (with Copilot awareness)
TASK:       Write {module_path}
SPEC:       docs/spec_v9.md#{section}
INTERFACE:  docs/module_interfaces.md#{module_name}
DEPENDS ON: {comma-separated existing modules}
SKILLS:     {comma-separated skill names}
COPILOT:    .github/copilot-instructions.md loaded
INFRA:      import LoggingAgent FactCheckAgent HealthCheckAgent SecurityAgent
REVIEW:     CodeReviewAgent must approve before commit
GATE:       pytest tests/test_{name}.py --cov --cov-fail-under=80
COMMIT:     feat(phaseN): add {module_name}
```

---

## Claude Integration

### Claude Role: Architect + Grader + Auditor

```
CLAUDE ROLES (unchanged from v8, enhanced for v9):
    ClaudeArchitectAgent    — interface design, dependency graph, schema
    ClaudeGraderAgent       — logic correctness review (not syntax)
    ClaudeHallucinationAgent— verify GPT-OSS/Groq outputs
    ClaudeFactCheckAgent    — validate pipeline design decisions
    ClaudeCostAgent         — INR calculations + budget review
    ClaudeCyberAgent (NEW)  — security review, threat model analysis
    ClaudeLearningAgent(NEW)— review knowledge graph growth patterns

CLAUDE SESSION WORKFLOW:
    1. Paste CLAUDE.md at start of session
    2. Present module interfaces for review
    3. Review CodeReviewAgent reports
    4. Grade logic correctness
    5. Flag hallucinations in design
    6. Approve or request changes
```
