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

**Status:** EXIT CRITERIA TECHNICALLY SATISFIED — AWAITING FOUNDER REVIEW (not self-declared COMPLETE)

### Entry Criteria
- application foundation stable — met (PP-001)

### Exit Criteria
The following are implemented and tested:

- ingredient normalization — met (PP-001)
- pantry matching — met (PP-001)
- price repository — met (PP-003: `app/repositories/price_repository.py`, read-only SQLite lookup, never returns zero for an unknown price)
- cost engine — met (PP-003: `app/domain/cost_engine.py`, implements TECHNICAL_SPEC.md section 13's package-purchase algorithm exactly against the frozen `CostEvaluation` contract)
- hard constraints — met (PP-001)
- deterministic ranking — met (PP-001; validated unchanged against real Module C cost output via `test_module_a_b_c_integration.py`)

**Note:** per this file's own Gate Rules ("no gate advances automatically because code exists" / "Founder / Product Owner remains final approval authority"), this gate is reported as exit-criteria-satisfied but is NOT self-declared COMPLETE here. Founder review and explicit approval are still required to close it, consistent with how G3 was handled.

### Evidence
- PP-001 PR #1 (merge commit `acb5278`), PP-002 PR #3 (merge commit `7cde50c`), PP-003 PR #5 (merge commit `39fbe62`, implementation head `aff4bd4`)
- unit tests (PP-001/PP-002/PP-003 backend suite, 245 passed, re-verified against `main` post-merge)
- integration tests (`backend/tests/integration/test_module_a_b_integration.py`, `test_module_a_b_c_integration.py`)
- regression fixtures: `backend/data/fixtures/lulu_sample.json` (ingestion edge cases); real-dataset QA report (see `CURRENT_STATUS.md`) — DEC-013's median/reference-price policy verified against ~2,699 real LuLu UAE products, including a post-merge local-database regeneration and `PriceRepository` read verification against that real dataset

### Approver
Founder / Product Owner (gate completion still requires explicit Founder/Product Owner approval per the Gate Rules below)

---

## G5 — Recipe Sources Ready

**Status:** IN PROGRESS — NOT COMPLETE

### Entry Criteria
- provider abstraction exists — met (PP-002, `app/recipe/provider.py`)

### Exit Criteria
- RecipeAPI.io adapter implemented — met (PP-002)
- provider contract tests pass — met (PP-002; cross-provider contract test parametrized over both providers)
- local curated provider implemented — **foundation only**; the provider class/mapping mechanism is implemented and tested, but ships with zero production recipe data
- provenance controls pass — met (PP-002; mandatory `source_label`/`provenance_note` enforced and tested)
- provider failure handling tested — met (PP-002; timeout/429/5xx/malformed-response/config-error all typed and tested)
- bounded request behavior verified — met (PP-002; bounded page size, bounded retry, bounded constructor overrides)

### Decision Prerequisites
- **DEC-012 remains OPEN and is not resolved by this update.** Per its own text, this gate cannot be marked COMPLETE until DEC-012 (final curated dataset size/content) is satisfied — the local curated provider is intentionally left at "foundation only."

### Evidence
- PP-002 PR #3 (merge commit `7cde50c`)
- tests (`backend/tests/unit/test_recipeapi_io_adapter.py`, `test_local_curated_provider.py`, `test_provider_contract.py`)
- live smoke evidence: RecipeAPI.io live smoke test completed during PP-002 (4 requests: search, detail fetch, cuisine-filter discrepancy found and fixed, re-verified) — see `CURRENT_STATUS.md`

### Approver
Founder / Product Owner (gate completion still requires explicit Founder/Product Owner approval per the Gate Rules below, and cannot occur before DEC-012 resolves)

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
