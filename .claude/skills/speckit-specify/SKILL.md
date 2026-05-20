---
name: speckit-specify
description: "Create or update a feature specification from a natural language description by generating a branch, filling the spec template with user stories, functional requirements, success criteria, and running quality validation. Use when starting a new feature, creating specifications from user requirements, or capturing what a feature should do before planning begins."
---

# Spec Kit Specify Skill

## When to Use

- Starting a new feature that needs a spec before planning.
- The user describes a feature in natural language and needs it formalized.

## Inputs

- Natural language feature description from the user.
- Existing repo context (README, docs, constitution).

If the request is too vague to proceed, ask one focused question before starting.

## Workflow

1. **Generate a branch name**: Create a 2-4 word action-noun format name (e.g., "user-auth", "payment-flow"). Branch names must be lowercase, hyphen-separated, descriptive, and unique.

2. **Check existing branches and specs**:
   - Check remote branches: `git branch -r`
   - Check local branches: `git branch`
   - Check existing `specs/` directories to determine the next available feature number.
   - Determine the next sequential feature number (e.g., 001, 002, 003...).

3. **Execute the specification creation script**:
   - Run `.specify/scripts/bash/create-new-feature.sh` with the calculated feature number and short name.
   - Parse the output for FEATURE_DIR, FEATURE_SPEC, and BRANCH paths.

4. **Execute the specification workflow**:
   - Parse the user's description to extract: core user goals, actors/personas, functional requirements, success criteria, constraints.
   - Load `.specify/templates/spec-template.md` to understand required sections.
   - Fill all template sections with informed guesses based on the description.
   - Mark genuinely ambiguous decisions as `[NEEDS CLARIFICATION: <question>]`.
   - Limit clarification markers to a maximum of 3, prioritized by: scope > security/privacy > UX > technical details.
   - Focus on WHAT and WHY—no implementation details (no HOW).
   - All success criteria must be measurable and technology-agnostic.
   - Remove inapplicable sections entirely; do not leave "N/A" placeholders.

5. **Write the specification** to `specs/<feature>/spec.md` using the filled template.

6. **Validate quality**:
   - Create a checklist at `specs/<feature>/checklists/requirements.md`.
   - Validate: content quality, requirement completeness, feature readiness.
   - If clarification markers remain (≤3), present them as a Markdown table with suggested answers.
   - Resolve through user dialogue; update spec after each answer.

7. **Report completion**:
   - Output branch name, spec file path, and readiness status.
   - If all clarifications resolved: "Ready for planning with speckit-plan."
   - If clarifications remain: list them with context.

## Key Constraints

- Maximum 3 `[NEEDS CLARIFICATION]` markers total per spec.
- Make informed defaults for unspecified details; only ask when multiple interpretations significantly differ.
- Every requirement must be testable and verifiable without knowing the implementation.
- No implementation details—focus on user value and business needs.

## Outputs

- `specs/<feature>/spec.md` (the specification)
- `specs/<feature>/checklists/requirements.md` (quality validation checklist)
- New feature branch created and checked out

## Next Steps

After specifying:

- **Clarify** remaining ambiguities with speckit-clarify (optional but recommended).
- **Plan** implementation with speckit-plan.
