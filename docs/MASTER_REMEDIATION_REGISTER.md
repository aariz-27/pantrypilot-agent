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

## MR-001 — pytest dependency has an unresolved advisory (PYSEC-2026-1845)

**Date:** 2026-09-09
**Severity:** LOW
**Category:** SECURITY
**Component:** `backend/pyproject.toml` (`pytest` dev/test dependency)
**Status:** OPEN

### Exact Finding

`pip-audit` reports `pytest==8.4.2` is affected by PYSEC-2026-1845: "pytest through 9.0.2 on UNIX relies on directories with the `/tmp/pytest-of-{user}` name pattern, which allows local users to cause a denial of service or possibly gain privileges." The fix is `pytest>=9.0.3`, a major-version bump; `backend/pyproject.toml` currently pins `pytest>=8,<9`.

### Source

Module F Ticket 4.10 (backend dependency audit), run as part of security hardening work.

### Evidence

`pip-audit` output (backend venv, 2026-09-09):
```
Name   Version ID              Fix Versions
------ ------- --------------- ------------
pytest 8.4.2   PYSEC-2026-1845 9.0.3
```

### Root Cause

Upstream `pytest` advisory; not a PantryPilot code defect.

### Impact

`pytest` is a dev/CI-only dependency — it is never imported by, or bundled with, the deployed production process. The advisory itself requires local, unprivileged multi-user access to a shared UNIX host to exploit a predictable temp-directory path during test execution. GitHub Actions runners are single-tenant, ephemeral VMs, not shared multi-user hosts. **Actual exposure in PantryPilot's deployment model (single-tenant Oracle Cloud VM, CI on ephemeral runners) is assessed as minimal to none.**

### Affected Requirement / Decision

None (tooling dependency, not a product requirement).

### Dependency

None.

### Remediation Ticket

Not yet created. Two options for the Founder to choose between:
1. Take the major-version bump (`pytest>=9.0.3`) — requires re-verifying the full backend test suite against pytest 9's changes.
2. Formally record `BOUNDED ACCEPTED RISK` per `docs/SECURITY_ACCEPTANCE_MATRIX.md` Section 4, given the minimal actual exposure above.

Claude Code has not chosen between these — per `docs/SECURITY_ACCEPTANCE_MATRIX.md` Section 4, only the Founder may accept a security risk.

### Pull Request

Not created.

### Verification Evidence

CI's `security` job runs `pip-audit --ignore-vuln PYSEC-2026-1845` (see `.github/workflows/ci.yml`) so this single, documented, pending-decision finding does not perpetually fail every CI run while awaiting the Founder's decision above. This is a CI-configuration choice to keep the pipeline actionable, not a risk-acceptance decision.

### Residual Risk

Open pending Founder decision (see Remediation Ticket above).

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
