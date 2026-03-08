---
name: cicd-checkers
description: Rules for automated, un-mocked phase gate validation, test suites, and Phase 12 continuous integration mechanisms.
---

# CI/CD Checkers Skill (FA v2)

## Context
The Swarm operates under strict phase gates. Transitioning from development (e.g., Phase 2) to subsequent phases (e.g., Phase 3) requires passing a completely un-mocked, logical deployment array. 

## The Dynamic Audit (Rule 24)
-   Before marking any phase "COMPLETE", developers **must** run:
    ```bash
    python -m geosupply.cli.audit --level strict
    ```
-   **Zero Hardcoding**: CI/CD checklists cannot rely on hardcoded lengths. Example: do not assert `len(ALL_SCHEMAS) == 25`. Assert `len(ALL_SCHEMAS) == len(SCHEMA_VERSIONS)`. The CI/CD step validates consistency, not arbitrary counts.

## Test Enforcement
-   The CI/CD pipeline triggers Pytest directly via `$env:PYTHONPATH="src"; python -m pytest tests/unit/`.
-   **Warning as Errors**: Test suites MUST output 0 warnings. CI/CD runs with `-W error::DeprecationWarning` to force failure on deprecated features like `datetime.utcnow()`.
-   **Coverage Floor**: Code coverage is strictly gated at 80% per pipeline.

## Canary Deploys (Phase 12)
- Deployments of new tier-3 LLM reasoning agents deploy in a canary strategy. Monitor the outputs against the `HALLUCINATION_FLOOR = 0.70` via the `HallucinationCheckSubAgent`. If failure rates spike above 10% on evaluation, rollback automatically.
