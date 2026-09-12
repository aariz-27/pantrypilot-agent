# Runtime Ingredient Integration + 6-Result Recommendation Depth

Branch: `feature/admin-ingredient-dashboard` (continued from commit `0b3afb7`; see §0 for why no new branch was created). Not merged, not deployed, production untouched. Founder review required before either.

## 0. Branch decision

`git fetch origin` confirmed local `main` and `origin/main` are identical (`eb4f5b0`) — `main` has not advanced since the admin dashboard branch was created, and that branch was never pushed to `origin`. This ticket is a direct continuation of the admin dashboard's own documented known-gap ("Part A") plus a related, independently-motivated recommendation-depth fix ("Part B") — both close, related pieces of unfinished work on the same feature, not a separate concern. No rebase/merge was needed (nothing to reconcile against), and a separate integration branch would only have added an extra merge step with no benefit. Work continued directly on `feature/admin-ingredient-dashboard`.

## PART A — Runtime Ingredient Integration

### 1. Architecture: one coherent resolver, additive DB overlay

New module: `backend/app/repositories/runtime_ingredient_repository.py`. This is the **one** place canonical-ingredient/alias resolution is computed for every live call site — there is no second, competing resolver.

- **Built-in foundation (unchanged, frozen):** `app.domain.grocery_taxonomy.CANONICAL_GROCERY_INGREDIENTS` / `RECIPE_INGREDIENT_ALIASES`. Module A/B's own code (`ingredient_normalizer.py`, `ingredient_autocomplete.py`) was **not modified in its logic** — both already took `canonical_vocabulary`/`aliases` as parameters (or, for autocomplete, were extended to), so the merge happens entirely in the *callers* (the API route and the orchestrator), never inside the frozen domain functions themselves.
- **DB overlay (additive):** `canonical_ingredients` (active rows) ∪ built-in ids; `ingredient_aliases` (active rows) merged with `RECIPE_INGREDIENT_ALIASES`, built-in values always winning any raw key collision.
- **Precedence rules (ticket section 7), enforced at write time, not read time:**
  1. A built-in canonical id's identity is never redefined by a DB row. `AdminIngredientRepository.create_ingredient` now **rejects** creating a canonical_id that already exists in the built-in taxonomy (`ADMIN_CONFLICT`) — before this ticket it would have silently created an invisible, confusing duplicate.
  2. An alias already resolving (built-in OR DB) to canonical id A can never be silently repointed to canonical id B. `AdminIngredientRepository.create_alias` now checks `alias_conflicts_with_builtin()` in addition to its existing DB-vs-DB conflict check, and rejects with `ADMIN_CONFLICT` naming the built-in id it would have collided with.
  3. If the DB is unreachable, unmigrated, or the admin subsystem isn't configured for this deployment, every function falls back **silently** to the built-in-only result — proven by tests for: missing database file, missing `canonical_ingredients` table, missing `active` column (pre-migration shape), and `db_path=None`.

### 2. What now flows through the merged vocabulary

| Call site | File | Before | After |
|---|---|---|---|
| Public autocomplete | `backend/app/api/ingredients.py` | `CANONICAL_GROCERY_INGREDIENTS` / `GROCERY_INGREDIENT_ALIASES` direct | merged vocabulary via `get_merged_vocabulary(settings.price_db_path)` |
| Pantry normalization | `backend/app/agent/orchestrator.py` `_init_state` | built-in constants direct | `self._vocabulary` (computed once per orchestrator instance from `ingredient_db_path`) |
| Search-anchor grounding | `backend/app/agent/orchestrator.py` `_require_anchors_grounded_in_pantry` | built-in constants direct | `self._vocabulary` |
| Recipe-ingredient normalization | `backend/app/agent/tools.py` `normalize_recipe_ingredients` / `evaluate_recipe` / `evaluate_and_rank` | built-in constants hardcoded internally | optional `canonical_vocabulary`/`aliases` params, defaulting to built-ins (unchanged for any other caller), passed explicitly by the orchestrator |
| Pricing lookup | `PriceRepository` | unchanged | unchanged — already reads by canonical_id, which the merge now resolves correctly for admin-created ingredients too |

Also fixed as part of the cross-layer-consistency requirement (ticket section 10): autocomplete's built-in alias base changed from `GROCERY_INGREDIENT_ALIASES` to the superset `RECIPE_INGREDIENT_ALIASES` (the same base pantry normalization already used) — this can only ever add matches, never remove one an existing caller relied on (verified: every existing autocomplete unit test still passes unchanged).

### 3. Caching and invalidation

A short (30s) TTL, process-local cache keyed by `db_path`, invalidated immediately by every admin ingredient/alias mutation (`invalidate_runtime_ingredient_cache()`, called from `AdminIngredientRepository` after every successful create/reassign/deactivate, and after a `status` change in `update_ingredient`). This is the simplest design the ticket's own menu of options permitted: no cross-process pub/sub, no version numbers — an edit is visible in the *same* process on the very next request, and in *every* process (relevant only if ever scaled beyond the current single-VM competition deployment) within 30 seconds at the outside. `/ingredients/suggest` never queries the full table per keystroke — it reads the cached merged vocabulary.

### 4. Answering the ticket's explicit yes/no questions

- **Admin ingredient changes now affecting the public app: YES.**
- **Alias changes now affecting the public app: YES** (with built-in-collision prevention at write time).
- **Manual price integration status:** unchanged and already correct — proven end-to-end (admin creates ingredient → alias → price → public autocomplete resolves the alias → `PriceRepository` returns the exact manual price) by `tests/integration/test_admin_runtime_integration.py::test_new_canonical_ingredient_with_manual_price_resolves_through_public_pricing_identity`.

### 5. Incidental finding

The ticket's own illustrative example (`green_chili` / "Green Chili") turned out to already be a real built-in canonical ingredient in `app.domain.grocery_taxonomy` — a live demonstration, found while writing tests, of exactly the collision-prevention rule this ticket asked for: attempting to admin-create `green_chili` now correctly fails with `ADMIN_CONFLICT` rather than silently creating an invisible duplicate. Test fixtures use `dragonfruit_admin_test` instead.

## PART B — Six Initial Grounded Recommendations

### 6. Diagnosis recap (from the prior session's investigation, now acted on)

The actual bottleneck was never `MAX_FINAL_RECOMMENDATIONS = 3` (the `recommendations`/`additional_options` split point) — it was the agent's **stop policy**, which treated 3 feasible candidates as "sufficient" regardless of available quota. The frontend already correctly combines `recommendations` + revealed `additional_options` up to 6 (built in an earlier session) — it had nothing left to reveal because the backend rarely searched past 3.

### 7. Architecture decision: Option B (least conceptual debt)

`MAX_FINAL_RECOMMENDATIONS` stays **3** — unchanged. It is the top-tier "recommendations" cutoff, not a stop signal. Raising it to 6 (Option A) would have collapsed the `recommendations`/`additional_options` distinction the frontend's "Show more options" reveal already depends on, for zero behavioral benefit (the user-visible combined count is identical either way) at the cost of touching many existing tests that treat `MAX_FINAL_RECOMMENDATIONS` as the top-3 slice.

Instead, a new, independently-configurable **stop-policy target** was introduced: `AgentState.target_feasible_results` (default 6, from `Settings.target_feasible_results`). This drives:
- `sufficient_feasible_found` (the deterministic "is it OK to stop" signal the LLM reads): threshold raised from `MAX_FINAL_RECOMMENDATIONS` (3) to `target_feasible_results` (6).
- `reserve_depth_target_met`: now `feasible_anchor_candidate_count >= target_feasible_results` directly (previously an equivalent but less legible "+3 more" formula hardcoded to the old constant).
- `SYSTEM_POLICY` prose (`backend/app/agent/policy.py`): rewritten to say reaching 3 is no longer, by itself, a reason to stop — continue when a genuine, specificity-preserving avenue remains and the target isn't met yet; stop once `sufficient_feasible_found` is true OR the provider's inventory for the anchor is genuinely exhausted. The exact numeric target is never hardcoded into the fixed policy string (which must stay static per its own documented security invariant) — the LLM reads the live number from `state_summary.target_feasible_results`.

DEC-005 (the LLM controls stop/continue) is fully preserved: this is advisory evidence, never an enforced count. 2, 3, 4, or 5 results remain entirely legitimate outcomes when genuinely that's all the provider/constraints can support — this only changes what the model is told is *worth trying for*, never what it's forced to return.

### 8. RecipeAPI.io page size

`app.recipe.provider.MAX_PAGE_SIZE` (10, the free-plan value) is preserved as `SearchStrategy`'s own default. A new `ABSOLUTE_MAX_PAGE_SIZE = 100` safety ceiling replaces the old `le=MAX_PAGE_SIZE` Pydantic bound (was hard-blocking anything above 10). The adapter's own internal `min(strategy.page_size, MAX_PAGE_SIZE)` clamp — which would have silently re-capped every request back to 10 regardless of configuration — was removed; the adapter now trusts the already-validated `strategy.page_size`.

**Live-verified** (2026-09-13, one bounded `GET /recipes` call, `per_page=25`): the active trial plan accepts and honors `per_page=25` (`meta.per_page` echoed back as 25, 25 items actually returned, not silently capped). `Settings.recipeapi_page_size` therefore defaults to **25**.

### 9. New configuration variables

| Variable | Default | Bounds | Purpose |
|---|---|---|---|
| `PANTRYPILOT_RECIPEAPI_PAGE_SIZE` | 25 | 1–100 | Requested `per_page` for every RecipeAPI.io search. 25 is evidence-based (live-confirmed against the active trial), not guessed. |
| `PANTRYPILOT_TARGET_FEASIBLE_RESULTS` | 6 | 1–20 | How many strong, same-anchor feasible candidates the agent tries for before the stop-policy signal says "enough." Advisory only. |

**Quota impact of raising page size:** none additional per se — a larger page size returns *more results per request*, which typically means *fewer* total requests are needed to reach the same candidate count, not more. The actual driver of request volume is `target_feasible_results` (a higher target can lead the LLM to search further when genuinely worthwhile) — but this is explicitly bounded by the unchanged `MAX_SEARCH_ATTEMPTS = 3` and `MAX_EVALUATED_CANDIDATES = 20` ceilings (left unchanged — 20 remains adequate for a 6-candidate target, per the ticket's own instruction not to raise it without evidence).

### 10. Trial-expiry rollback

Set both variables back to their pre-trial-safe values:

```bash
PANTRYPILOT_RECIPEAPI_PAGE_SIZE=10
PANTRYPILOT_TARGET_FEASIBLE_RESULTS=3
```

restart the backend. No code change is required either direction. If the provider ever rejects an oversized `per_page` value outright (e.g. a downgraded plan), that surfaces as a normal `RecipeProviderError` on that one attempt (already handled gracefully — see §11) — it does not crash the application; only reducing the configured value restores full search capability.

### 11. Provider/quota failure preserves already-grounded results

This was found to be **already correct architecturally** (`app.agent.tools.execute_search` converts any `RecipeProviderError` into a typed per-attempt outcome, never letting it propagate as an exception) — verified end-to-end with a new regression test (`test_rate_limit_on_a_later_attempt_preserves_earlier_grounded_results`): a successful first search followed by a rate-limited second attempt still returns the first attempt's 3 grounded candidates in `recommendations`, never discarding them. No production code change was needed for this specific requirement; only the proving test was added.

### 12. Sonnet's role — unchanged, re-verified

No change was made to the agent's action schema or tool layer. Existing tests (`test_llm_attempt_to_supply_recipe_content_is_rejected_as_malformed`, `test_agent_action_schema_has_no_score_field`, and others) already comprehensively prove Sonnet cannot supply recipe names/ingredients/quantities/instructions/prices/scores — these continue to pass unchanged.

## Testing summary

- Backend: **751 passed** (0 regressions from the 730 the admin dashboard commit left; +21 net new/rewritten across Part A and Part B — some pre-existing tests were deliberately updated to the new 6-candidate threshold, per the ticket's own explicit instruction not to preserve the old value "merely because it is historical").
- Frontend: **204 passed**, unchanged — the ticket confirmed the existing 6-visible/"Show more" implementation is already correct and explicitly asked not to rewrite it; verified, not touched.
- Live acceptance: full admin login → create ingredient → alias → manual price → public autocomplete recognition → price resolution walkthrough run against a real `uvicorn` process and an isolated `/tmp` database (never the real `data/pantrypilot.db`, confirmed untouched by unchanged mtime), then cleaned up.
- Quality gates: governance validation PASS, secret scan clean, `pip-audit` 0 vulnerabilities, frontend `oxlint` 0 warnings, `npm run build` succeeds, `npm audit` 0 vulnerabilities.

## ALLOWED_ORIGINS bug — status clarification (ticket section 36)

- **What was fixed in the admin dashboard branch (commit `0b3afb7`):** a *different*, unrelated bug — `Settings.admin_username` / `admin_password_hash` / `admin_session_secret` did not map to the required `PANTRYPILOT_ADMIN_*` env var names (no alias configured), so a real deployment exporting those exact variables would still report the admin subsystem as unconfigured. Fixed with explicit `validation_alias` + `populate_by_name`, with regression tests (`tests/unit/test_config.py`).
- **What remains open, NOT fixed (correctly, per this ticket's explicit instruction not to silently fix unrelated things):** `Settings.allowed_origins` (a pre-existing, unrelated field) crashes the application at startup if `ALLOWED_ORIGINS` is set as a real environment variable to its own documented comma-separated format (e.g. `ALLOWED_ORIGINS=https://example.com`) — `pydantic-settings` attempts a JSON-decode of any env-sourced value for a `list[str]`-typed field *before* the field's own parsing validator runs, and a plain comma-separated string is not valid JSON. This was not exercised by any existing test because every test constructs `Settings(allowed_origins=[...])` directly in Python (bypassing environment-variable parsing entirely). **Does not block this integration** (this ticket's own live acceptance testing simply avoided setting `ALLOWED_ORIGINS` as a real env var). **Recommended as a small, separate, explicitly-authorized ticket** — it is a real production-configuration risk (a Founder setting `ALLOWED_ORIGINS` in the real production `.env` following its own documented format would crash the app at boot) but is unrelated to ingredient resolution or recommendation depth, and CLAUDE.md's scope-control rules direct fixing it only under its own authorized ticket.

## Local startup

```bash
cd backend
export PANTRYPILOT_ADMIN_USERNAME=founder
export PANTRYPILOT_ADMIN_PASSWORD_HASH=<output of: python scripts/hash_admin_password.py>
export PANTRYPILOT_ADMIN_SESSION_SECRET=<output of: python -c "import secrets; print(secrets.token_urlsafe(32))">
export PANTRYPILOT_RECIPEAPI_PAGE_SIZE=25       # optional, this is already the default
export PANTRYPILOT_TARGET_FEASIBLE_RESULTS=6    # optional, this is already the default
python scripts/migrate_admin_schema.py --db data/pantrypilot.db
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

## Production deployment (prepare only — not executed)

Identical to the admin dashboard's own deployment guide (`docs/admin/ADMIN_DASHBOARD.md` §8), with two additions to step 3 ("configure admin secrets"): also set `PANTRYPILOT_RECIPEAPI_PAGE_SIZE=25` and `PANTRYPILOT_TARGET_FEASIBLE_RESULTS=6` in the production `.env` / systemd `EnvironmentFile`. No new database migration beyond the admin dashboard's own (`scripts/migrate_admin_schema.py`) is required — Part A introduced no new tables, only new read paths over the existing ones.

## Rollback

Same as `docs/admin/ADMIN_DASHBOARD.md` §9 (frontend release symlink revert, backend code revert, database restore only if the migration itself is suspected). Additionally: reverting `PANTRYPILOT_RECIPEAPI_PAGE_SIZE`/`PANTRYPILOT_TARGET_FEASIBLE_RESULTS` to their pre-trial values (§10 above) requires no code change and no restart-order dependency on anything else.

## Confirmation: production untouched

No code was pushed or merged. No migration was run against `data/pantrypilot.db` (mtime unchanged throughout this session, verified before and after all live testing). All live testing used isolated temporary databases, cleaned up afterward. The one live RecipeAPI.io call made (§8) was a single bounded `GET /recipes` request, consistent with the ticket's own "a small number of live provider calls is acceptable... prefer fixtures/tests first" instruction.
