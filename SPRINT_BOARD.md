# PantryPilot Sprint Board

## Purpose

This file tracks the currently planned and active implementation tickets for PantryPilot.

It is intentionally lightweight.

It must not replace:

- `CURRENT_STATUS.md`
- `DECISION_REGISTER.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- GitHub pull requests

The board exists to show what work is queued, active, blocked, under review, or completed.

---

## Status Values

Use only:

- BACKLOG
- READY
- IN_PROGRESS
- IN_REVIEW
- BLOCKED
- DONE

---

## Current Sprint Goal

Establish the governed application foundation and then deliver the PantryPilot MVP through bounded implementation tickets.

---

## Active Ticket

None. PP-001, PP-002, and PP-003 have all been completed and merged (see "Completed" below). The next coding ticket will be added once the Founder/Product Owner authorizes it.

---

## Ready Queue

None. PP-001, PP-002, and PP-003 have been completed and merged. The next coding ticket will be added once the Founder/Product Owner authorizes it.

---

## Backlog

Delivered by PP-001 (see Done section below): repository/application scaffold, backend health endpoint, shared domain DTOs, ingredient normalization, pantry matching, constraint evaluator (subset), deterministic ranker.

Delivered by PP-002 (see Done section below): `RecipeProvider` abstraction, RecipeAPI.io adapter, `LocalCuratedRecipeProvider` foundation (zero production data — DEC-012 still open).

Delivered by PP-003 (see "Completed" below): LuLu UAE grocery ingestion pipeline (M14), read-only `PriceRepository` (M10), deterministic `CostEngine` (M11), DEC-013 median reference-pricing policy.

Remaining planned implementation areas include:

- frontend scaffold
- agent tool layer
- agent orchestrator
- recommendation API (`/api/recommend` end-to-end wiring)
- frontend/backend integration
- observability
- deployment
- release verification
- final curated recipe dataset content (blocked on DEC-012)
- grocery taxonomy gap-fill / manual curated price entries (optional, informed by PP-003's QA report — 381 of 2,699 real products remain unmapped)

These are implementation areas, not automatically authorized tickets.

Each item must become a governed `PP-XXX` ticket before Claude Code begins implementation.

---

## Blocked

None currently.

Potential future blockers include unresolved decision triggers in:

`docs/governance/decision_triggers.json`

---

## In Review

None currently.

---

## Completed

### PP-003 — Grocery Pricing Ingestion, Reference Price Repository, and Deterministic Cost Engine

**Status:** DONE
**Priority:** P0
**Requirements:** FR-11, FR-12, AR-07, AR-12 (implemented)
**Decision Dependencies:** DEC-013 (recorded, APPROVED)
**Branch:** `feature/pp-003-pricing-cost-engine` (merged)

**Objective:**
Deterministic LuLu UAE grocery ingestion (M14: raw → mapped → reference), a read-only reference-price repository (M10), and a deterministic purchase-cost engine (M11), plugging into PP-001's frozen `CostEvaluation`/constraint-evaluator/ranker contracts unchanged.

**Notes:**
Merged via PR #5 (merge commit `39fbe62`, implementation head `aff4bd4`). 245 backend tests passed (160 existing + 85 new, including a post-review correction pass); governance validation and CI both passed (Backend Checks, Frontend Checks, Governance Validation), and were re-verified after merge against `main`. Ingested and QA'd against the real 2,699-product Founder-provided LuLu export (see `CURRENT_STATUS.md` for full statistics: 213 canonical ingredients priced, 1,734 products mapped, 419 unresolved, 11 incompatible-unit groups correctly excluded rather than merged, 9 duplicates detected). Independent review found and fixed four correctness issues (unjustified canonical-mapping defaults, an unreliable LuLu productType label, silent range/additive package under-parsing, keyword-ordering bugs) before final approval — see `CURRENT_STATUS.md` for the corrected figures. Post-approval, pre-merge, the real local SQLite database was regenerated from the Founder's LuLu export using the merged scripts and `PriceRepository` was verified to read it correctly. No LLM classification anywhere in the pipeline. Raw dataset and generated SQLite DB are gitignored, never committed. See `CURRENT_STATUS.md` and `DECISION_REGISTER.md` (DEC-013) for full evidence.

---

### PP-002 — Grounded Recipe Retrieval Layer

**Status:** DONE
**Priority:** P0
**Requirements:** FR-08, FR-09, FR-19, FR-20, AR-03, AR-04, AR-13 (implemented); FR-16, AR-05 (foundation only)
**Decision Dependencies:** DEC-012 (remains OPEN; not resolved by this ticket)
**Branch:** `feature/pp-002-grounded-recipe-retrieval` (merged)

**Objective:**
Provider-neutral `RecipeProvider` abstraction, the RecipeAPI.io adapter (primary live provider), and the `LocalCuratedRecipeProvider` foundation, so PantryPilot can search and retrieve real existing recipes and map them into the shared `Recipe` domain model. The future agent (search strategy, pagination/reformulation, stop decisions) is explicitly not part of this ticket.

**Notes:**
Merged via PR #3 (merge commit `7cde50c`, implementation head `521a482`). 151 backend tests passed at merge; a subsequent comprehensive Module A+B validation pass added 9 A+B integration tests (160 total), finding no defects, architectural drift, or scope drift. Governance validation and CI passed. An old API key committed to git history predating this ticket (`bfdde3e`) was found; `backend/.env` was removed from tracking (`eb50929`), though the revoked credential remains visible in that commit's historical deletion diff since history was not rewritten. The Founder rotated/revoked the exposed credential; the current key is not committed. Live-verified against the real RecipeAPI.io API (4 requests) during implementation, including a cuisine-filter case-sensitivity discrepancy that was found, fixed, and re-verified live; live-verified again (3 requests) with the rotated key during post-merge closure. Explicitly out of scope: pricing/cost engine, LLM/agent orchestration, `/api/recommend` end-to-end wiring, frontend, deployment, TheMealDB, bulk-inventing the final curated dataset. See `docs/REQUIREMENTS_TRACEABILITY.md` and `CURRENT_STATUS.md` for full evidence.

---

### PP-001 — Application Foundation and Deterministic Core

**Status:** DONE
**Priority:** P0
**Requirements:** FR-06, FR-10, FR-13, FR-14, AR-02, AR-12, AR-13 (implemented); FR-12 (foundation/input-shape only)
**Decision Dependencies:** None
**Branch:** `feature/pp-001-foundation-deterministic-core` (merged)

**Objective:**
FastAPI application foundation and the deterministic core (ingredient normalization, pantry matching, constraint evaluation, deterministic ranking) required to evaluate and rank grounded recipe candidates, with an explicit `CostEvaluation` input plug-point for the future Cost Engine.

**Notes:**
Merged via PR #1 (merge commit `acb5278`, implementation head `5865b79`). 79 backend tests passed, 2 warnings; governance validation and CI passed. Explicitly out of scope: RecipeAPI.io integration, LocalCuratedRecipeProvider, real grocery pricing repository/cost engine, LLM/agent orchestration, frontend, deployment. `/api/health`'s `database` status remains `not_configured` until the reference DB exists. Documented soft ranking assumption retained: no cuisine preference → neutral cuisine score 1.0. See `docs/REQUIREMENTS_TRACEABILITY.md` and `CURRENT_STATUS.md` for full evidence.

---

Governance foundation work completed so far includes:

- core architecture documentation
- data architecture
- data integrity policy
- performance/reliability policy
- quality/security/test strategy
- threat model
- security acceptance matrix
- API integration standards
- decision register
- decision trigger registry
- approval gates
- remediation register
- requirements traceability
- project history
- status update workflow
- migration/release policy
- observability/operations policy
- independent review checklist
- pull request template
- implementation ticket template

---

## Ticket Entry Template

When adding a real implementation ticket, use:

### PP-XXX — Short Title

**Status:** READY  
**Priority:** P0 / P1 / P2  
**Requirements:** FR-XX, AR-XX  
**Decision Dependencies:** None / DEC-XXX  
**Branch:** `feature/pp-xxx-short-title`

**Objective:**  
One clear outcome.

**Notes:**  
Short operational note only.

---

## Board Rules

1. No ticket moves to `READY` without explicit Founder / Product Owner authorization.
2. Claude Code may only implement tickets marked `READY`.
3. When implementation begins, move ticket to `IN_PROGRESS`.
4. When PR opens, move ticket to `IN_REVIEW`.
5. If a blocking decision or defect appears, move ticket to `BLOCKED`.
6. After merge and closure, move ticket to `DONE`.
7. Do not use this board to hide unresolved findings or decisions.
8. GitHub remains authoritative for actual branch/PR/merge state.
