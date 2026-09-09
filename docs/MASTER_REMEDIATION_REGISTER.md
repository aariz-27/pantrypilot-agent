# PantryPilot Master Remediation Register

## Purpose

This document is the canonical register for all confirmed review findings, defects, security issues, performance concerns, reliability problems, governance issues, and remediation items.

Important rule:

A finding must not exist only in:

- chat
- Claude Code output
- PR comments
- temporary notes

If a finding matters, it must be recorded here.

---

## Finding Identifier

Every finding uses the format:

`MR-###`

Examples:

- MR-001
- MR-002
- MR-003

`MR` identifies the finding only.

Implementation work must still use a normal governed implementation ticket.

Do not create a second parallel ticket system.

---

## Allowed Status Values

Use only:

- OPEN
- IN_REMEDIATION
- FIXED
- RE_VERIFIED
- DEFERRED
- NOT_YET_IMPLEMENTED
- INVALIDATED

---

## Severity Levels

Use:

- CRITICAL
- HIGH
- MEDIUM
- LOW
- INFORMATIONAL

---

## Categories

Examples:

- FUNCTIONAL
- ARCHITECTURE
- SECURITY
- DATA_INTEGRITY
- PERFORMANCE
- RELIABILITY
- CONCURRENCY
- IDEMPOTENCY
- TESTING
- MIGRATION
- OBSERVABILITY
- GOVERNANCE
- PROVIDER
- UI/UX

---

# Current Findings

## MR-001 — pytest dependency vulnerable to predictable temp-directory path (PYSEC-2026-1845)

**Date:** 2026-09-09 (opened) / 2026-09-09 (remediated and re-verified, same day)
**Severity:** MEDIUM (GitHub advisory rating: MODERATE; CVSS 3.1 `AV:L/AC:L/PR:N/UI:N/S:C/C:L/I:L/A:L`)
**Category:** SECURITY
**Component:** `backend/pyproject.toml` (`pytest` / `pytest-asyncio` dev/test dependencies)
**Status:** RE_VERIFIED

### Exact Finding

`pip-audit` reported `pytest==8.4.2` affected by PYSEC-2026-1845 (aliases `GHSA-6w46-j5rx-g56g`, `CVE-2025-71176`, CWE-379): pytest's `tmp_path`/`tmpdir` fixture machinery creates its base temp directory at a predictable path, `/tmp/pytest-of-{username}`, with a predictable per-run subdirectory scheme. On a UNIX host shared with other local users, another unprivileged local user can pre-create/symlink that predictable path before the victim's pytest run, causing a denial of service or a symlink-based integrity issue. Fixed in `9.0.3`.

**Correction to the original write-up:** this finding was first recorded stating the vulnerable code path was likely unused by PantryPilot's tests. That was wrong — a `grep` scoping error (run from inside `backend/`, so the pattern doubled the path prefix and silently matched nothing) produced a false negative. A corrected search from the repo root found `tmp_path` used across 11 test files and dozens of test functions (`backend/tests/agent/conftest.py`'s `price_db` fixture — used broadly across agent tests — plus `test_price_repository.py`, `test_cost_engine.py`, `test_db_connection.py`, `test_review_needed_expansion.py`, `test_module_a_b_c_integration.py`, `test_module_c_pricing_gap_resolution.py`, `test_health_endpoint.py`, `test_grocery_ingestion_pipeline.py`, `test_recommend_endpoint.py`, `test_butter_apple_carrot_data_quality_fix.py`). Confirmed empirically: running the full suite created `/tmp/pytest-of-{user}/pytest-0/` with 200+ per-test subdirectories holding throwaway SQLite fixture databases. The vulnerable functionality is genuinely exercised, on every test run, including every CI run.

### Source

Module F Ticket 4.10 (backend dependency audit). Initial finding and its correction both surfaced during Founder-requested review-only follow-up on this same ticket.

### Evidence

`pip-audit` output (backend venv, before fix):
```
Name   Version ID              Fix Versions
------ ------- --------------- ------------
pytest 8.4.2   PYSEC-2026-1845 9.0.3
```
`pip-audit` output (backend venv, after fix, no ignore flag): `No known vulnerabilities found`.

### Root Cause

Upstream `pytest` advisory; not a PantryPilot code defect. Compounded by `backend/pyproject.toml` pinning `pytest-asyncio>=0.24,<1`, which hard-conflicts with `pytest>=9` (pip's resolver refuses the pair) — the fix required a coordinated two-package major-version bump, not a single-line change.

### Impact

`pytest` is dev/CI-only — never imported by or bundled with the deployed production process. Exploiting the advisory requires a second, unprivileged local user account on the same host racing to pre-create the predictable path before the victim's pytest run. GitHub Actions runners are single-tenant ephemeral VMs (no second local user); a developer machine is single-user; the documented Oracle VM competition deployment is single-tenant by design, so no second local user exists there either, unless that design assumption is violated. Even in a successful exploit, the data at risk is disposable test-fixture SQLite databases, not real secrets or the production reference DB (gitignored, never touched by tests). **Net assessment: genuinely exercised by the test suite, but low realistic exploitability given the competition deployment topology — fixed anyway because the fix carries zero measured regression risk (see Verification Evidence).**

### Affected Requirement / Decision

None (tooling dependency, not a product requirement).

### Dependency

None.

### Remediation Ticket

`MODULE-F` (this ticket) — Founder approved "FIX NOW" for this specific remediation only, scoped to the dependency change alone (no application code, no other Module F functionality, no unrelated dependency upgrades).

### Pull Request

#16 (`feature/module-f-security-persistence` → `main`, not merged)

### Verification Evidence

- `backend/pyproject.toml`: `pytest>=8,<9` → `pytest>=9.0.3,<10`; `pytest-asyncio>=0.24,<1` → `pytest-asyncio>=1.4,<2`. Resolves to `pytest==9.1.1`, `pytest-asyncio==1.4.0` in this environment (both satisfy the floor).
- Full backend suite: **650/650 passed**, same 2 pre-existing unrelated deprecation warnings, no new failures or warnings — verified twice: once in an isolated scratch venv (pre-approval investigation) and once for real in the project's own venv (post-approval implementation).
- `pip-audit` (no ignore, both the project venv and a genuinely fresh venv with `pip install --upgrade pip setuptools wheel && pip install '.[dev]'`): `No known vulnerabilities found`.
- Transitive dependencies checked directly: `pluggy` (1.6.0), `iniconfig` (2.3.0), `packaging` (26.3) all unchanged — no churn beyond the two intended packages.
- CI's `security` job `--ignore-vuln PYSEC-2026-1845` exception removed from `.github/workflows/ci.yml`; plain `pip-audit` now expected to pass clean.

### Residual Risk

None identified. The advisory's fixed version is installed and verified; no downgrade path exists in the declared range (`<10` still requires `>=9.0.3`).

---

# Finding Template

Use the following structure for every future finding.

## MR-XXX — Finding Title

**Date:** YYYY-MM-DD  
**Severity:** HIGH  
**Category:** SECURITY  
**Component:** Example module/service  
**Status:** OPEN  

### Exact Finding

Describe precisely what is wrong.

Do not write vague statements such as:

> Security needs improvement.

Instead write something actionable such as:

> RecipeAPI adapter accepts an externally supplied base URL, allowing a model-controlled argument to influence outbound HTTP destination.

### Source

Where was the finding discovered?

Examples:

- ChatGPT independent PR review
- Claude self-review
- automated security scan
- regression test
- manual testing
- production/staging observation

### Evidence

Reference actual evidence where possible:

- PR number
- file path
- line range
- test failure
- CI job
- screenshot
- log excerpt
- evidence folder

### Root Cause

Describe the underlying cause.

Example:

> Provider URL ownership was not enforced at the adapter boundary.

### Impact

Describe what can happen if the issue is not fixed.

### Affected Requirement / Decision

List relevant:

- requirement IDs
- decision IDs
- ADRs
- architecture rules

### Dependency

List any prerequisite decision/ticket.

Use:

`None`

if there is no dependency.

### Remediation Ticket

Implementation ticket ID.

Example:

`PP-017`

Do not put the MR identifier here as the implementation ticket.

### Pull Request

PR number or:

`Not created`

### Verification Evidence

After remediation, record:

- tests
- code evidence
- review evidence
- CI result

### Residual Risk

Describe any remaining risk after remediation.

Use:

`None identified`

only after verification supports that statement.

---

# Finding Lifecycle

Normal flow:

```text
OPEN
  ↓
IN_REMEDIATION
  ↓
FIXED
  ↓
RE_VERIFIED
FIXED means implementation claims the issue has been corrected.

RE_VERIFIED means independent review/testing has confirmed the correction.

A finding must not be closed merely because Claude says it is fixed.

Deferred Findings

A finding may be DEFERRED only when:

it is documented
reason is documented
impact is understood
future trigger is recorded
Founder / Product Owner approves deferral where material

Security risk acceptance must also follow the Security Acceptance Matrix and Decision Register rules.

Invalidated Findings

Use INVALIDATED only when evidence shows:

finding was incorrect
affected code/path does not exist
technical assumption was false

Do not delete the historical record.

Document why it was invalidated.

Regression Rule

Every confirmed defect should receive a regression test unless technically impossible.

If no regression test is created, record:

why automation is technically impractical
manual verification method
residual risk
Repeated Defect Rule

If the same defect class appears twice:

do not continue relying only on manual review.

Consider creating:

CI validator
architecture rule
database constraint
test invariant
shared validation helper
workflow check

The structural control should be linked back to the relevant findings.

Escape-Path Requirement

Every remediation must ask:

Does another path exist that can produce the same defect or bypass the fix?

Examples:

another API route
alternate provider
cache path
direct repository call
agent tool path
import script
alternate call sequence

If yes, remediation scope must address the invariant rather than patching only one call site.

Review Responsibility
Claude Code

May:

identify findings
implement remediation
provide first-pass verification

Must not:

mark a significant finding RE_VERIFIED based solely on self-review
ChatGPT

Must:

independently inspect relevant code/diff/tests
verify remediation
identify escape paths
recommend status change
Founder / Product Owner

Approves:

accepted risk
material deferral
final merge
Repository Rule

This file is the authoritative finding register.

PR comments and chat discussions may reference findings, but this register remains the canonical source.
