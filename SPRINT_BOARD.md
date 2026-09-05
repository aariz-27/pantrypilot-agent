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

None.

---

## Ready Queue

None. PP-001 has been completed and merged (see Done section below). The next coding ticket will be added once the Founder/Product Owner authorizes it.

---

## Backlog

Delivered by PP-001 (see Done section below): repository/application scaffold, backend health endpoint, shared domain DTOs, ingredient normalization, pantry matching, constraint evaluator (subset), deterministic ranker. Real price data and full cost calculation are still outstanding — PP-001 only delivered the typed `CostEvaluation` input plug-point, not the Cost Engine/Price Repository themselves.

Remaining planned implementation areas include:

- frontend scaffold
- price repository
- cost engine
- RecipeProvider abstraction
- RecipeAPI.io adapter
- LocalCuratedRecipeProvider
- agent tool layer
- agent orchestrator
- recommendation API
- frontend/backend integration
- observability
- deployment
- release verification

These are implementation areas, not automatically authorized tickets.

Each item must become a governed `PP-XXX` ticket before Claude Code begins implementation.

---

## Blocked

None currently.

Potential future blockers include unresolved decision triggers in:

`docs/governance/decision_triggers.json`

---

## In Review

None.

---

## Completed

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
