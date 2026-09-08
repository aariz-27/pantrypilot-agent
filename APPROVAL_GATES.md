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

**Status:** EXIT CRITERIA TECHNICALLY SATISFIED — AWAITING FOUNDER REVIEW (not self-declared COMPLETE)

### Entry Criteria
- deterministic core ready — met (G4 exit criteria technically satisfied; PP-001/PP-003)
- recipe sources ready — met for the primary live path (G5 exit criteria technically satisfied for RecipeAPI.io; PP-002). The local curated route remains foundation-only pending DEC-012, and the orchestrator correctly treats it as a narrow, cuisine-gated route (`is_approved_local_curated_intent`) rather than a general fallback.

### Exit Criteria
Agent can:

- choose search strategy — met (`AgentOrchestrator._handle_search`, `backend/app/agent/orchestrator.py`; `FR-07`)
- inspect candidates — met (`AgentOrchestrator._build_observation` surfaces top candidates and aggregate signals back to the LLM each decision step)
- use deterministic tools — met (`app/agent/tools.py` composes the frozen Module A-C pipeline unchanged: normalization -> pantry matching -> pricing -> cost -> hard constraints -> ranking; the LLM never performs any of these calculations itself, per `DEC-006`)
- reformulate search — met (`FR-15`; distinct-search-signature enforcement in `AgentOrchestrator._handle_search` prevents repeating an identical failed strategy)
- paginate when justified — met (`REL-05`; `AgentOrchestrator._require_paginatable`/`_next_page_strategy`, only permitted after a prior successful `has_more` attempt)
- stop early — met (LLM-issued `STOP` action, `AgentOrchestrator.run`)
- stop on bounded exhaustion — met (`AR-11`, `REL-06`, `REL-07`; hard-coded `MAX_SEARCH_ATTEMPTS=3` / `MAX_EVALUATED_CANDIDATES=20` in `backend/app/agent/state.py`, enforced in Python independent of what the LLM requests)
- return grounded recommendations — met (`FR-17`, `FR-19`, `FR-20`; the agent never fabricates recipe content — all candidates trace to `RecipeAPIIOAdapter`/`LocalCuratedRecipeProvider` output through the unchanged Module B mapping layer)

**Not yet met / out of this gate's proven scope:**
- the ~15s worst-case latency target (`REL-02`) is structurally bounded (attempt/candidate caps) but not measured or tested — see `docs/REQUIREMENTS_TRACEABILITY.md`
- no `/api/recommend` HTTP endpoint exposes the orchestrator yet, so "agentic business path" is proven at the orchestrator/integration-test level, not via a live public API route
- no frontend exists, so there is no end-user-facing demo of this path yet

Agentic proof tests pass: 34 orchestrator scenario tests (`backend/tests/agent/test_orchestrator_scenarios.py`), plus `backend/tests/agent/test_actions.py`, `test_observations_and_state.py`, and `backend/tests/unit/test_llm_provider_anthropic.py` — all included in the 378 backend tests passing on `main` as of this update (2026-09-08).

### Decision Prerequisites
- DEC-010 must be satisfied before production agent runtime is finalized — **satisfied**: DEC-010 is APPROVED/CLOSED (PR #13, merge commit `987c98d`); Claude Sonnet 5 / `AnthropicLLMProvider` is the frozen competition runtime path.

### Evidence
- Implementation PRs: #11 `feature/module-d-agent-orchestration` (merge commit `5170c03`, implementation head `98497ad`, with two same-PR review-fix commits `c790b6f` and `bd13409`); #12 `test/module-a-d-integration-validation` (merge commit `cecaf2c`, implementation head `c1ec90b`)
- Decision-closure PR: #13 `docs/dec-010-close-competition-llm` (merge commit `987c98d`)
- Preceding unblocking work: #9 `feature/module-c-final-pricing-gap-resolution`, #10 `quality/pre-module-d-full-codebase-audit`
- Agent tests: `backend/tests/agent/` (`test_orchestrator_scenarios.py`, `test_actions.py`, `test_observations_and_state.py`), `backend/tests/unit/test_llm_provider_anthropic.py`
- Integration validation: PR #12 closed remaining orchestrator integration gaps against the existing frozen Module A-B-C integration tests (`backend/tests/integration/test_module_a_b_integration.py`, `test_module_a_b_c_integration.py`) that the orchestrator's tool layer composes unchanged
- Demo scenario: `backend/scripts/live_smoke_full_pipeline.py` — a manual, Founder-authorized, one-off live run of the real connected pipeline (`AgentOrchestrator` -> real Anthropic API -> real RecipeAPI.io -> real packaged reference price DB). This is **not** part of the automated test suite or CI (it refuses to run under pytest); it is evidence of a real live run having been exercised, not a repeatable automated demo.
- Full backend test count: 378 passed, 2 warnings (unrelated `httpx`/`anyio` deprecation warnings), verified against `main` on 2026-09-08

### Approver
Founder / Product Owner — this gate is reported here as exit-criteria-satisfied (for the orchestrator-level scope described above) but is **not self-declared COMPLETE**. Per this file's own Gate Rules ("No gate advances automatically" / "Code completion alone does not equal gate completion" / "Founder / Product Owner remains final approval authority"), explicit Founder review and approval are still required to close G6, consistent with how G3 and G4 are handled above.

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
