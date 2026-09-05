# PantryPilot Project History

## Purpose

This file is the append-only chronological history of major PantryPilot project events.

It records what happened and when.

It is NOT the authoritative source for current project status.

For current status, use:

`CURRENT_STATUS.md`

---

## History Rules

1. Append new entries only.
2. Do not rewrite historical statements simply because the project later changes.
3. Current-state facts belong in `CURRENT_STATUS.md`.
4. Decision changes belong in `DECISION_REGISTER.md`.
5. Implementation/PR state belongs in GitHub and ticket traceability records.
6. Findings belong in `docs/MASTER_REMEDIATION_REGISTER.md`.

---

## 2026-08-12 — Initial Master Blueprint

PantryPilot Master Project Blueprint v3.0 established the initial competition architecture and scope.

Major decisions included:

- existing recipes only
- RecipeAPI.io as primary source
- single-agent architecture
- deterministic Python matching/cost/ranking
- React frontend
- FastAPI backend
- SQLite local data
- one-time UAE grocery price acquisition
- no runtime grocery scraping
- no recipe generation
- no multi-agent system

---

## 2026-08 — RecipeAPI.io Feasibility Testing

RecipeAPI.io was manually tested before implementation.

Key findings included:

- single-ingredient searches were generally more focused
- multi-ingredient searches were broad/relevance-based rather than strict AND
- pagination could still return useful candidates
- supported cuisine filters materially improved some searches
- `max_prep_time` did not represent total meal time
- ingredient units and optional flags were structured and useful
- some provider metadata could not be treated as medical/dietary authority
- Indian/Pakistani/desi recipe coverage was weak for several tested dish names

The primary provider decision remained GO.

---

## 2026-08 — Regional Recipe Strategy Revised

TheMealDB was removed from the competition MVP to simplify integration and testing.

A small read-only `LocalCuratedRecipeProvider` was selected for approved Indian/Pakistani/desi coverage gaps.

Both RecipeAPI.io and the local curated source remain behind the common RecipeProvider abstraction.

---

## 2026-08 — Technical Specification Revised

`TECHNICAL_SPEC.md` and `AGENTS.md` were revised to reflect actual RecipeAPI.io behavior and the new provider strategy.

Major updates included:

- TheMealDB removal
- local curated regional source
- bounded pagination/reformulation strategy
- total meal time handled locally as prep + cook
- optional/non-food ingredient handling
- updated testing requirements
- updated provider failure behavior

---

## 2026-09 — Master Blueprint Revised

The Master Blueprint was revised to v3.1 REVISED FINAL so the product/architecture document matched the updated technical specification.

---

## 2026-09 — Repository Governance Foundation Started

A dedicated PantryPilot GitHub repository was created.

The repository was designated as the authoritative project memory.

The project adopted the following operating model:

- Founder / Product Owner: final decision and merge authority
- ChatGPT: Solution Architect and independent reviewer
- Claude Code: bounded implementation and test-writing agent

Governance documents began to be added before product coding.

---

## 2026-09 — Governance Documents Added

The following governance/architecture documents were established:

- `CURRENT_STATUS.md`
- `DECISION_REGISTER.md`
- `docs/AI_DELIVERY_OPERATING_MODEL.md`
- `CLAUDE.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- `docs/SYSTEM_CONTEXT.md`
- `docs/DATA_ARCHITECTURE.md`
- `docs/DATA_INTEGRITY_POLICY.md`
- `docs/PERFORMANCE_RELIABILITY_POLICY.md`
- `docs/QUALITY_SECURITY_TEST_STRATEGY.md`
- `docs/THREAT_MODEL.md`
- `docs/SECURITY_ACCEPTANCE_MATRIX.md`
- `docs/API_INTEGRATION_STANDARDS.md`
- `docs/governance/decision_triggers.json`
- `APPROVAL_GATES.md`
- `docs/MASTER_REMEDIATION_REGISTER.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`

No product implementation had been authorized at this stage.

---

## 2026-09-05 — PP-001 Merged: Application Foundation and Deterministic Core

The first authorized implementation ticket, PP-001 — Application Foundation and Deterministic Core, was implemented on `feature/pp-001-foundation-deterministic-core`, reviewed, corrected, and merged into `main` via PR #1.

Delivered:

- FastAPI backend scaffold with typed configuration (`SecretStr`-protected API keys) and a `GET /api/health` endpoint
- shared provider-neutral domain models (Recipe, RecipeIngredient, CandidateEvaluation, CostEvaluation, UserConstraints)
- ingredient normalizer (M08 foundation) with a seed canonical/alias vocabulary
- deterministic pantry matcher (M09): coverage, missing ingredients, duplicate-safe matching, UNKNOWN handling
- constraint evaluator (M12 subset): exclusions, strict cuisine, optional max-total-time, recipe usability/provenance foundations
- deterministic ranker (M13): approved 45/30/15/10 weighted score with full deterministic tie-breaking
- typed `PantryPilotError` / `InvalidInputError` application errors
- 79 unit/integration tests

ChatGPT independent review identified three correctness/security findings during this cycle, all fixed on the same branch before merge:

1. UNKNOWN required recipe ingredients were not reducing pantry coverage (excluded from the coverage denominator entirely) — fixed so they count in the denominator without being fabricated a canonical ID or counted as matched.
2. Incomplete cost with a supplied budget was classified as feasible — fixed by rejecting that state as indeterminate (`RejectionReason.BUDGET_INDETERMINATE_COST_INCOMPLETE`) rather than scoring it.
3. `rank_candidates()` could be reached with a `hard_constraint_pass=True` candidate whose own cost/budget fields contradicted that flag, bypassing `evaluate_constraints()` via an alternate call sequence — closed with a second-line defensive re-check inside the ranker.

Explicitly out of scope for this ticket: RecipeAPI.io integration, LocalCuratedRecipeProvider, real grocery pricing repository/cost engine, LLM/agent orchestration, frontend, deployment. `/api/health`'s `database` status remains `not_configured` until the reference DB exists. One documented soft ranking assumption remains: no cuisine preference scores a neutral 1.0.

Merge commit: `acb527823550de5aa1e88bebae866ec8d73a573f`. Implementation head (pre-merge): `5865b79ba25e03a22b86757894968047aa83bddc`. Final verification: 79 backend tests passed (2 warnings), governance validation passed, CI passed, working tree clean, local `main` synchronized with `origin/main`.

`APPROVAL_GATES.md` G3 (Implementation Foundation Ready) is not marked complete: the frontend scaffold does not yet exist. G3 remains IN PROGRESS pending that condition and explicit Founder/Product Owner gate approval.

---

## 2026-09-05 — PP-002 Merged: Grounded Recipe Retrieval Layer

The second authorized implementation ticket, PP-002 — Grounded Recipe Retrieval Layer, was implemented on `feature/pp-002-grounded-recipe-retrieval`, reviewed, corrected, and merged into `main` via PR #3.

Delivered:

- provider-neutral `RecipeProvider` Protocol with typed `SearchStrategy`/`SearchResultItem`/`SearchResult`, and `dedupe_search_results()` for (provider, provider_recipe_id) identity
- RecipeAPI.io adapter (primary live provider), verified against the provider's real live documentation before implementation and against real live calls afterward: bounded page size, explicit 5s timeout, bounded retry (timeout/network/5xx only, never 429), full provider error-code mapping, provenance-preserving mapping into the shared `Recipe`/`RecipeIngredient` DTOs, no provider-specific field leakage
- `LocalCuratedRecipeProvider` foundation: read-only, storage-agnostic, zero bundled production recipe data, mandatory `source_label`/`provenance_note` provenance, duplicate-ID rejection
- typed `RECIPE_PROVIDER_*`/`RECIPE_NOT_FOUND` errors
- 63 new tests at initial merge, mocked HTTP only in the automated suite

Pre-existing issue found and remediated during this ticket: a real RecipeAPI.io API key had been committed directly to `main` (predating this ticket) via an explicit `git add` that bypassed `.gitignore`. `backend/.env` was untracked from git as this branch's first commit, and the Founder rotated the affected key. A session mistake (an overly broad diff-based secret scan that printed the pre-rotation key value into terminal output, not into any committed artifact) was disclosed immediately when it occurred.

Independent review found and fixed two further issues before merge:

1. `RecipeAPIIOAdapter`'s `timeout_seconds`/`max_retries` constructor parameters had no bounds validation, allowing a caller to bypass the required bounded-retry/bounded-timeout reliability guarantees. Fixed by validating both at construction time (`ALLOWED_MAX_RETRIES = (0, 1)`, `0 < timeout_seconds <= 5.0`), raising before any HTTP client is built or used.

A live smoke test (4 requests total) additionally found that RecipeAPI.io's cuisine filter requires lowercase enum values; a capitalized filter value matched zero results. Fixed by lowercasing the cuisine value inside the adapter and re-verified live.

Merge commit: `7cde50c4742ad397fb1e3e9586d8264b822721f2`. Implementation head (pre-merge): `521a482145662e619843a4c9fbe46b3e143ac7e9`. Final verification at merge: 151 backend tests passed (2 warnings), governance validation passed, CI passed.

A subsequent comprehensive Module A+B validation pass (before this post-merge closure) added 9 new integration tests (`backend/tests/integration/test_module_a_b_integration.py`) composing provider-mapped recipes through the full PP-001 deterministic pipeline. All 7 requested scenarios passed; no defects, architectural drift, or scope drift were found. Total suite: 160 passed, 2 warnings.

Explicitly out of scope for this ticket: pricing/cost engine, LLM/agent orchestration, `/api/recommend` end-to-end wiring, frontend, deployment, TheMealDB, and bulk-inventing the final curated dataset (DEC-012 remains OPEN — not resolved by this ticket).

`APPROVAL_GATES.md` G4 (Core Deterministic Engine Ready) and G5 (Recipe Sources Ready) are not marked complete: G4 is blocked on the price repository/cost engine (not started); G5 is blocked on DEC-012. Both remain IN PROGRESS pending those conditions and explicit Founder/Product Owner gate approval.
