---
name: qa-testers
description: The absolute QA parameters for enforcing the ZERO MOCKS rule and real-world logic testing parameters across the swarm architecture.
---

# QA Testers Skill (FA v2)

## Context
GeoSupply AI mandates logical testing boundaries to verify multi-agent system behavior.

## The ZERO MOCK Policy Detailed
1.  **Do Not Patch Code You Control**: If you are testing `InputSanitiserWorker`, do NOT `patch('geosupply.workers.input_sanitiser_worker.InputSanitiserWorker.process')`. Test the real worker. Input dirty text, expect clean text.
2.  **State Machine Validation (G2)**: QA must test `_transition()` logic on `BaseAgent` implementations. Supply an invalid transition array mapping and assert `InvalidStateTransition` exception fires.
3.  **Real Failures for Error Control**:
    -   To test database recovery, **drop the table**. 
    -   To test API keys missing, clear the environment variables array (`patch.dict(os.environ, clear=True)`).
    -   To test signing capability, aggressively backdate the `issued_at` timestamp rather than mocking `time.time()`.

## Cross-Phase Audit Logic
QA ensures tests exist for the audit CLI itself:
-   A test **MUST** verify the audit CLI flags (`--level strict`) run Pytest programmatically inside `geosupply.cli.audit`. 
-   QA asserts that if a developer implements a `BaseWorker` and uniquely forgets to override `process()`, the audit CLI script must forcefully fail with exit code `1`.
