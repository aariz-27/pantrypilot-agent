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

**Status:** NOT STARTED

### Entry Criteria
- G2 complete
- first implementation ticket explicitly authorized

### Exit Criteria
- repository/application scaffold exists
- backend boots
- frontend boots
- health endpoint works
- baseline tests run
- CI baseline passes
- no unauthorized scope added

### Evidence
- implementation ticket
- PR
- test results
- GitHub merge
- post-merge reconciliation

### Approver
Founder / Product Owner

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
