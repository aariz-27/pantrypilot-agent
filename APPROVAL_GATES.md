# PantryPilot Approval Gates

## Purpose

This document defines project readiness gates.

A gate does not advance automatically because code exists.

Each gate requires:
- entry criteria
- exit criteria
- evidence
- required decisions
- explicit approval

---

## G0 — Business Direction Approved

**Status:** COMPLETE

### Entry Criteria
- problem defined
- target user defined
- product objective defined

### Exit Criteria
- PantryPilot concept approved
- scope direction approved
- agentic positioning approved

### Evidence
- Master Blueprint

### Approver
Founder / Product Owner

---

## G1 — Architecture Ready

**Status:** COMPLETE

### Entry Criteria
- product direction approved

### Exit Criteria
- Master Blueprint current
- TECHNICAL_SPEC.md current
- AGENTS.md current
- TECHNICAL_ARCHITECTURE.md approved
- SYSTEM_CONTEXT.md approved
- DATA_ARCHITECTURE.md approved
- major technical decisions recorded
- open decision triggers identified

### Required Decisions
- approved provider strategy
- approved deterministic/LLM responsibility split
- approved application stack

### Evidence
- docs/TECHNICAL_ARCHITECTURE.md
- docs/SYSTEM_CONTEXT.md
- docs/DATA_ARCHITECTURE.md
- DECISION_REGISTER.md

### Approver
Founder / Product Owner

---

## G2 — Governance Foundation Ready

**Status:** COMPLETE

### Entry Criteria
- G1 architecture substantially defined

### Exit Criteria
- CLAUDE.md complete
- AI_DELIVERY_OPERATING_MODEL.md complete
- CURRENT_STATUS.md complete
- DECISION_REGISTER.md complete
- decision_triggers.json complete
- APPROVAL_GATES.md complete
- MASTER_REMEDIATION_REGISTER.md created
- REQUIREMENTS_TRACEABILITY.md created
- security/test policies created
- PR template created
- ticket traceability structure created

### Evidence
Repository governance documents

### Approver
Founder / Product Owner

---

## G3 — Implementation Foundation Ready

**Status:** IN PROGRESS — NOT COMPLETE

### Entry Criteria
- G2 complete — met
- first implementation ticket explicitly authorized — met (PP-001)

### Exit Criteria
- repository/application scaffold exists — partially met: `backend/` scaffold exists; `frontend/` does not exist
- backend boots — met
- frontend boots — **not met** (frontend does not exist yet)
- health endpoint works — met (`GET /api/health`)
- baseline tests run — met (79 backend tests passed)
- CI baseline passes — met (`.github/workflows/ci.yml`: Backend Checks, Frontend Checks, Governance Validation all pass; Frontend Checks currently no-ops since no `frontend/` exists)
- no unauthorized scope added — met

**Remaining condition to close this gate:** a frontend scaffold must exist and boot before G3 can be marked COMPLETE. This gate is intentionally left IN PROGRESS rather than forced COMPLETE.

### Evidence
- Implementation ticket: PP-001 — Application Foundation and Deterministic Core
- PR: #1
- Merge commit: `acb527823550de5aa1e88bebae866ec8d73a573f`
- Implementation head (pre-merge): `5865b79ba25e03a22b86757894968047aa83bddc`
- Test results: 79 backend tests passed, 2 warnings
- GitHub merge: confirmed (`main`, fast-forwarded, working tree clean)
- Post-merge reconciliation: this update (`CURRENT_STATUS.md`, `SPRINT_BOARD.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, `PROJECT_HISTORY.md`)

### Approver
Founder / Product Owner (gate completion, once the frontend condition above is met, still requires explicit Founder/Product Owner approval per the Gate Rules below)

---

## G4 — Core Deterministic Engine Ready

**Status:** NOT STARTED

### Entry Criteria
- application foundation stable

### Exit Criteria
The following are implemented and tested:

- ingredient normalization
- pantry matching
- price repository
- cost engine
- hard constraints
- deterministic ranking

### Evidence
- module PRs
- unit tests
- integration tests
- regression fixtures

### Approver
Founder / Product Owner

---

## G5 — Recipe Sources Ready

**Status:** NOT STARTED

### Entry Criteria
- provider abstraction exists

### Exit Criteria
- RecipeAPI.io adapter implemented
- provider contract tests pass
- local curated provider implemented
- provenance controls pass
- provider failure handling tested
- bounded request behavior verified

### Decision Prerequisites
- DEC-012 satisfied before local curated provider is declared complete

### Evidence
- provider PRs
- tests
- live smoke evidence where appropriate

### Approver
Founder / Product Owner

---

## G6 — Agentic Business Path Ready

**Status:** NOT STARTED

### Entry Criteria
- deterministic core ready
- recipe sources ready

### Exit Criteria
Agent can:

- choose search strategy
- inspect candidates
- use deterministic tools
- reformulate search
- paginate when justified
- stop early
- stop on bounded exhaustion
- return grounded recommendations

Agentic proof tests must pass.

### Decision Prerequisites
- DEC-010 must be satisfied before production agent runtime is finalized

### Evidence
- agent tests
- integration tests
- demo scenario

### Approver
Founder / Product Owner

---

## G7 — End-to-End Staging Ready

**Status:** NOT STARTED

### Entry Criteria
- agentic backend path works

### Exit Criteria
- React connected to FastAPI
- recommendation journey works
- progress states work
- source attribution works
- error states work
- staging deployment works
- critical regression suite passes

### Evidence
- staging URL
- smoke test
- screenshots/video if useful
- CI evidence

### Approver
Founder / Product Owner

---

## G8 — Competition Release Ready

**Status:** NOT STARTED

### Entry Criteria
- staging ready

### Exit Criteria
- P0 acceptance criteria pass
- security acceptance conditions pass
- no unresolved critical/high defect without explicit accepted risk
- RecipeAPI.io health verified
- SQLite build verified
- frontend build verified
- deployment stable
- demo scenario rehearsed
- source/usage requirements checked
- known-good release tagged

### Decision Prerequisites
- DEC-011 deployment platform satisfied

### Evidence
- final test report
- deployment evidence
- release tag
- remediation status
- approval record

### Approver
Founder / Product Owner

---

## G9 — Submission Complete

**Status:** NOT STARTED

### Entry Criteria
- G8 complete

### Exit Criteria
- final competition submission completed
- required project/demo material submitted
- LinkedIn sharing completed if required
- final repository/build reference recorded

### Approver
Founder / Product Owner

---

# Gate Rules

1. No gate advances automatically.
2. Code completion alone does not equal gate completion.
3. Open blocking decisions prevent advancement.
4. Critical unresolved findings prevent release unless explicitly accepted as bounded risk.
5. Evidence must point to actual repository/PR/test/deployment state.
6. Founder / Product Owner remains final approval authority.
