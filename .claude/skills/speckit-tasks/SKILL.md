---
name: speckit-tasks
description: "Generate a dependency-ordered tasks.md organized by user story with phased execution, parallel markers, and strict checklist format. Use when the implementation plan is ready and the user needs an executable task breakdown before coding begins."
---

# Spec Kit Tasks Skill

## When to Use

- The implementation plan exists and you need a structured, executable task breakdown.

## Inputs

- `specs/<feature>/plan.md` (required)
- `specs/<feature>/spec.md` (required for user stories)
- Optional: `data-model.md`, `contracts/`, `research.md`, `quickstart.md`

If plan.md is missing, ask the user to run speckit-plan first.

## Workflow

1. **Validate prerequisites**: Run `.specify/scripts/bash/check-prerequisites.sh --json --require-plan` from repo root. Parse FEATURE_DIR and AVAILABLE_DOCS. All paths must be absolute.

2. **Load design artifacts**:
   - **REQUIRED**: Read `plan.md` for tech stack, architecture, and file structure.
   - **REQUIRED**: Read `spec.md` for user stories with priorities (P1, P2, P3).
   - **IF EXISTS**: Read `data-model.md` for entities and relationships.
   - **IF EXISTS**: Read `contracts/` for API specifications.
   - **IF EXISTS**: Read `research.md` for technical decisions and constraints.
   - **IF EXISTS**: Read `quickstart.md` for integration scenarios.

3. **Extract and map user stories to technical components**:
   - Extract tech stack from plan.md.
   - Extract user stories from spec.md with priority levels.
   - Map entities, endpoints, and architectural decisions to corresponding user stories.
   - Build a dependency graph showing story completion order.

4. **Organize tasks into phases**:
   - **Setup**: Project structure, dependencies, configuration, ignore files.
   - **Foundational**: Shared infrastructure blocking all user stories (models, DB schema, auth).
   - **User Stories (P1, P2, P3)**: One sub-phase per story, ordered by priority.
   - **Polish**: Cross-cutting concerns, documentation, performance, final validations.

   Within each user story phase:
   - Tests (if TDD requested) precede implementation tasks.
   - Models → Services → Endpoints/CLI → Integration tasks.

5. **Apply strict checklist format** (non-negotiable):

   Every task line must follow exactly:
   ```
   - [ ] [TaskID] [P] [Story] Description — path/to/file.ext
   ```

   Rules:
   - `- [ ]` checkbox always required.
   - `[TaskID]`: Sequential ID like T001, T002, T003...
   - `[P]`: Optional parallelization marker — include only if the task has no blocking dependencies.
   - `[Story]`: User story label (e.g., [US1], [US2]) — apply ONLY in user story phases, never in Setup/Foundational/Polish.
   - `Description`: Specific enough for an AI to execute independently without additional context.
   - File path: Mandatory for every implementation task.

6. **Write tasks.md** to `specs/<feature>/tasks.md`.

## Task Organization Strategy

Tasks flow: shared infrastructure (Setup) → blocking prerequisites (Foundational) → independent user story phases → cross-cutting polish. Within each story: tests → models → services → endpoints → integration.

## Key Rules

- Tasks must be specific enough to execute independently without additional context.
- [P] marker indicates no blocking dependencies — safe to parallelize.
- Story labels only in user story phases (never Setup/Foundational/Polish).
- File paths are mandatory for every implementation task.

## Outputs

- `specs/<feature>/tasks.md` with dependency-ordered, phase-structured task list

## Next Steps

After tasks are generated:

- **Implement** with speckit-implement.
- **Create GitHub issues** with speckit-taskstoissues.
