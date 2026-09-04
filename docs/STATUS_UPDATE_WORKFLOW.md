# PantryPilot Status Update Workflow

## 1. Purpose

This document defines how project status is updated after implementation, review, remediation, merge, and release activity.

The goal is to keep repository status accurate and prevent:

- stale project state
- contradictory documents
- chat-only progress
- ticket/PR drift
- premature readiness claims

---

## 2. Authoritative Status Sources

Different repository files own different types of state.

### CURRENT_STATUS.md

Owns:

- current project phase
- current gate
- active ticket
- blockers
- current maturity
- immediate next work

### DECISION_REGISTER.md

Owns:

- architecture/product/technical decisions
- decision status
- unresolved decisions
- decision rationale

### APPROVAL_GATES.md

Owns:

- gate definitions
- gate readiness
- approval conditions

### docs/REQUIREMENTS_TRACEABILITY.md

Owns:

- requirement → ticket → test → PR → evidence mapping

### docs/MASTER_REMEDIATION_REGISTER.md

Owns:

- confirmed findings
- remediation state
- independent re-verification status

### PROJECT_HISTORY.md

Owns:

- append-only major historical events

### GitHub

Owns:

- actual commits
- branches
- pull requests
- merge state
- CI execution

No chat message or AI memory overrides repository state.

---

## 3. Status Update Principle

Project status should reflect evidence, not intention.

Do not write:

> M03 complete

because implementation work started.

Write completion only when defined exit criteria and evidence exist.

---

## 4. Ticket Start Workflow

When a ticket is approved for implementation:

Update:

### CURRENT_STATUS.md

Set:

- active ticket
- current phase
- current gate
- relevant blocker state

### REQUIREMENTS_TRACEABILITY.md

For affected requirements:

- populate Ticket
- change status from `DESIGNED` to `IN_IMPLEMENTATION`

Do not mark unrelated requirements as in implementation.

---

## 5. During Implementation

Claude Code may update implementation-local files required by the authorized ticket.

Claude must not independently change project maturity or approval-gate state.

If implementation discovers a material new decision:

1. stop affected implementation
2. document the ambiguity
3. update `DECISION_REGISTER.md`
4. obtain Founder / Product Owner decision
5. resume only after decision is approved

If implementation discovers a confirmed defect or governance problem:

record it in:

`docs/MASTER_REMEDIATION_REGISTER.md`

---

## 6. Pull Request Opened

When a PR is opened:

Update affected requirement rows:

- PR number
- status = `IN_REVIEW`

`CURRENT_STATUS.md` should identify the ticket as under review if it is the active project item.

Do not mark code `IMPLEMENTED` before merge.

---

## 7. Claude Self-Review

Before independent review, Claude must provide:

- ticket scope confirmation
- implementation summary
- files changed
- tests added/changed
- test results
- security review
- performance/reliability review
- known limitations
- explicit statement of any deviation

Claude self-review is evidence input.

It is not independent approval.

---

## 8. ChatGPT Independent Review

ChatGPT review must inspect the actual:

- PR diff
- code
- tests
- relevant repository contracts

Review order:

1. authorization
2. decision compliance
3. requirement compliance
4. scope control
5. architecture
6. correctness
7. data integrity
8. security
9. performance
10. reliability
11. concurrency
12. tests
13. escape paths
14. operability
15. governance closure

If a confirmed finding exists:

record it in the Master Remediation Register.

---

## 9. Correction Pass

If review requires corrections:

### CURRENT_STATUS.md

Keep ticket active.

### REQUIREMENTS_TRACEABILITY.md

Keep affected requirements at:

`IN_REVIEW`

### MASTER_REMEDIATION_REGISTER.md

Set relevant finding:

`IN_REMEDIATION`

Claude then performs only the authorized correction scope.

---

## 10. Final Re-Review

After corrections:

ChatGPT must inspect the actual correction diff and relevant tests.

If remediation is proven:

finding may move:

`FIXED` → `RE_VERIFIED`

If implementation is acceptable for merge:

ChatGPT records review approval/recommendation.

Founder remains final merge authority.

---

## 11. Founder Merge

After Founder merges the PR:

Update affected requirement rows:

- PR number
- evidence
- status = `IMPLEMENTED`

Do not automatically change to `VERIFIED` unless required independent verification is complete.

---

## 12. Post-Merge Closure

After merge:

### CURRENT_STATUS.md

Update:

- remove completed active ticket
- update phase if appropriate
- update blockers
- update next authorized work
- update maturity only if evidence supports it

### REQUIREMENTS_TRACEABILITY.md

Update:

- implementation state
- test references
- evidence links/paths

### MASTER_REMEDIATION_REGISTER.md

Update findings tied to merged remediation.

### PROJECT_HISTORY.md

Append only if the merge represents a significant milestone.

Not every small PR requires a project-history entry.

---

## 13. Gate Advancement

A gate may advance only when its defined exit criteria are satisfied.

Before changing gate status:

1. inspect `APPROVAL_GATES.md`
2. verify all required evidence
3. verify blocking decisions
4. verify critical findings
5. verify required tests
6. obtain Founder / Product Owner approval

Then update:

- `APPROVAL_GATES.md`
- `CURRENT_STATUS.md`

Gate state must remain consistent between both files.

---

## 14. Maturity State Workflow

Allowed capability maturity states:

- `DESIGNED`
- `FOUNDATION_IMPLEMENTED`
- `BUSINESS_PATH_IMPLEMENTED`
- `PROVIDER_GATED`
- `PILOT_BLOCKED`
- `PILOT_READY`
- `PRODUCTION_READY`

These represent system capability, not ticket completion.

### DESIGNED

Architecture and requirements exist.

### FOUNDATION_IMPLEMENTED

Technical scaffold and foundational infrastructure work.

### BUSINESS_PATH_IMPLEMENTED

Primary end-to-end business logic exists.

### PROVIDER_GATED

Business path exists but external provider/data dependency prevents broader readiness.

### PILOT_BLOCKED

Known blocker prevents pilot use.

### PILOT_READY

Defined pilot acceptance conditions pass.

### PRODUCTION_READY

Production release conditions pass.

Do not skip maturity states without explicit evidence and approval.

---

## 15. Decision Trigger Workflow

Before starting work associated with a decision trigger:

Check:

`docs/governance/decision_triggers.json`

If trigger is crossed and decision is unresolved:

STOP.

Do not:

- infer the answer
- select a default
- let Claude choose
- hide the decision inside implementation

Resolve the decision through `DECISION_REGISTER.md`.

---

## 16. Remediation Workflow

Confirmed defect:

```text
Review Finding
    ↓
MASTER_REMEDIATION_REGISTER
    ↓
Authorized Remediation Ticket
    ↓
Claude Correction
    ↓
Independent Re-Review
    ↓
RE_VERIFIED

Do not delete findings after remediation.

The historical record must remain.

17. Escape-Path Review

Every important fix or control change must ask:

Is there another path that can bypass this control or reproduce the same defect?

Examples:

another API endpoint
alternate recipe provider
local curated provider
cache path
direct repository call
agent tool call
frontend bypass
database import path

Fix the invariant where possible, not just one observed call site.

18. Status Consistency Check

Before completing any governance update, check for contradictions between:

CURRENT_STATUS.md
APPROVAL_GATES.md
DECISION_REGISTER.md
REQUIREMENTS_TRACEABILITY.md
MASTER_REMEDIATION_REGISTER.md
PROJECT_HISTORY.md

Example contradiction:

CURRENT_STATUS.md says G5 complete while APPROVAL_GATES.md still lists G5 as NOT STARTED.

Such inconsistencies must be corrected before closure.

19. AI Agent Responsibilities
Claude Code

May:

implement authorized ticket
write tests
perform self-review
update ticket-specific traceability when authorized

Must not:

approve own merge
resolve product decisions
advance gates independently
declare system production-ready
conceal findings
ChatGPT

Responsible for:

architecture governance
independent review
compliance review
escape-path analysis
remediation verification
readiness recommendation
Founder / Product Owner

Responsible for:

material decisions
ticket authorization
risk acceptance
gate approval
final merge authority
20. Competition-Speed Rule

Governance must support delivery rather than create unnecessary ceremony.

For PantryPilot competition MVP:

update only documents materially affected
avoid duplicate status records
keep evidence concise
automate mechanical checks where useful
do not create documents solely for appearance

Control quality must remain high even when the process is lightweight.
