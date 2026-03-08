# Governance: Sync Checks

## Mandatory Checks Before Marking a Phase Complete
1. Code inventory updated in `actual_state/01_implementation_baseline.md`.
2. Phase reconciliation updated in `actual_state/02_phase_status_reconciliation.md`.
3. `python -m geosupply.cli.audit --level strict` reviewed.
4. Unit test suite and relevant integration tests pass.
5. Coverage target and warning policy reviewed.
6. Risk register items for touched domains reviewed.

## Anti-Drift Check
If counts, statuses, or contracts changed in code, update FA v3 `actual_state` docs in the same change set.
