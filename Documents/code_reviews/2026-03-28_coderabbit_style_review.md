<!-- markdownlint-disable MD022 MD029 MD032 -->

# Code Review Report (CodeRabbit-Style)

Date: 2026-03-28
Scope: Recent venv/bootstrap and related repo changes
Reviewer mode: CodeRabbit-style local review

Note:
- A native `coderabbit` CLI/integration is not available in this environment (`Get-Command coderabbit` failed), so this is a CodeRabbit-style manual review based on actual diffs and file reads.

## Findings

### 1. HIGH - Non-essential Node dependency tree added to Python-first repo without guardrails
- Files: `package.json`, `package-lock.json`
- Why this matters:
  - Adds a large transitive dependency surface (`skillfish` + many packages) in a repo that currently gates quality through Python audit/test flow.
  - No CI/verification path in this review for npm lockfile integrity, license compliance, or vulnerability scanning.
  - Increases supply-chain and maintenance risk without clear runtime need for the current bootstrap objective.
- Recommendation:
  - Remove these files from the same change set unless a concrete Node-based workflow is required now.
  - If needed, add explicit CI checks (`npm ci --ignore-scripts`, audit/sca policy, lockfile owner/process docs).

### 2. MEDIUM - Bootstrap verification omits practical test execution
- File: `scripts/venv_bootstrap.ps1`
- Evidence:
  - Verification command runs:
    - `python -m geosupply.cli.audit --categories breakage,logic,oversight,connectivity --level strict`
  - This excludes the `practical` category used by `audit.py` to invoke integrated pytest checks.
- Why this matters:
  - A "green bootstrap" can pass structural checks while still missing runtime regressions that full practical tests would detect.
- Recommendation:
  - Add an option to run practical checks by default for CI-grade bootstrap (or enable by default with a `-SkipPractical` opt-out).

### 3. MEDIUM - Packaging tool upgrades run unconditionally on every bootstrap
- File: `scripts/venv_bootstrap.ps1`
- Evidence:
  - Always executes: `pip install --upgrade pip setuptools wheel` before drift check.
- Why this matters:
  - Increases runtime and introduces unnecessary network dependence for idempotent runs.
  - Can fail in restricted/offline environments even when no project dependencies changed.
- Recommendation:
  - Gate toolchain upgrades behind a switch (e.g., `-UpgradeTools`) or include them in the drift hash decision path.

### 4. LOW - Dev install state can be downgraded after non-dev force sync
- File: `scripts/venv_bootstrap.ps1`
- Evidence:
  - State writes `dev_installed = $InstallDev` whenever sync occurs.
- Why this matters:
  - A forced sync without `-InstallDev` can mark state false even if dev extras were previously installed.
  - Causes avoidable reinstall churn on subsequent `-InstallDev` runs.
- Recommendation:
  - Persist `dev_installed = ($InstallDev -or $previousDev)` or detect installed extras directly.

### 5. LOW - Logging variable introduced but not used
- File: `src/geosupply/cli/audit.py`
- Evidence:
  - `logger = logging.getLogger(__name__)` added; no corresponding log calls added in this patch hunk.
- Why this matters:
  - Minor hygiene/noise issue.
- Recommendation:
  - Either use logger in new code paths or remove until needed.

## Positive Notes

- `BaseAgent` capability initialization now correctly preserves subclass-declared capabilities:
  - File: `src/geosupply/core/base_agent.py`
  - Change aligns MoE capability advertisement with class declarations.

- `InfraSupervisor` now copies class-level `agents` into an instance list:
  - File: `src/geosupply/supervisors/infra_supervisor.py`
  - Avoids accidental class-level mutation side effects.

- `sitecustomize.py` path bootstrap is clean and minimal:
  - File: `sitecustomize.py`
  - Improves local venv usability by avoiding manual `PYTHONPATH` exports.

## Suggested Next Patch Set

1. Update `scripts/venv_bootstrap.ps1`:
- Add `-RunPractical` (or include practical checks by default).
- Add `-UpgradeTools` switch; avoid unconditional packaging upgrades.
- Preserve `dev_installed` state across non-dev syncs.

2. Decide on npm metadata files:
- If not required now, drop `package.json` and `package-lock.json` from this branch.
- If required, add CI and documentation for Node supply-chain governance.

3. Minor cleanup:
- Remove or use the new `logger` in `src/geosupply/cli/audit.py`.

## Validation Status

- Reviewed via direct file reads and diff inspection for:
  - `scripts/venv_bootstrap.ps1`
  - `sitecustomize.py`
  - `src/geosupply/core/base_agent.py`
  - `src/geosupply/supervisors/infra_supervisor.py`
  - `src/geosupply/subagents/rag_pipeline_subagent.py`
  - `src/geosupply/cli/audit.py`
  - `Documents/fa_v3_architecture/actual_state/05_venv_bootstrap.md`
  - `package.json`
  - `package-lock.json`
