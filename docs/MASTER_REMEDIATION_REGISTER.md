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

No findings recorded.

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
