# Unified Ingredient Resolution

Branch: `fix/unified-ingredient-resolution`. Not merged, not deployed, production untouched. Founder review required before either.

## 0. Problem

Production symptom: a single valid ingredient (e.g. "lamb chops") typed as free text could return zero recipes, while adding a second ingredient (e.g. "rice") could suddenly surface one. "chicken" typed without selecting an autocomplete suggestion could not be searched at all. Root cause, confirmed by inspection and live RecipeAPI.io calls before any code was changed:

1. **Frontend**: the autocomplete's Enter-key handler only committed free text when the debounced suggestion list was *empty*. A generic term like "chicken" always has suggestions (specific cuts: chicken breast, chicken wings, ...), so Enter never committed the raw text the user actually typed, and the only alternative was to accept a needlessly narrower suggestion — exactly the "silent over-narrowing" this ticket's own principles forbid.
2. **Backend, outbound**: pantry ingredients that resolved to a PantryPilot canonical id (e.g. `lamb_chops`) were sent to RecipeAPI.io as that id naively de-slugged to `"lamb chops"`. Confirmed live: RecipeAPI.io's own ingredient catalogue lists the **singular** `"Lamb chop"` (id 1139), and its `GET /ingredients?search=` endpoint does **not** stem plurals server-side — querying `"lamb chops"` returns zero candidates, not even the singular one, so there was nothing for any candidate-side matching to compare against.
3. **Backend, no anchor at all**: "chicken" has no generic PantryPilot canonical id (only specific cuts, per the existing "don't auto-narrow" principle), so it was previously rejected outright as "not present in the user's pantry" before ever reaching a provider search.

## 1. Identity model (never conflated)

| | Concept | Example |
|---|---|---|
| A | User input | `"chiken brest"` |
| B | Interpreted user intent | `"chicken breast"` |
| C | PantryPilot canonical identity | `chicken_breast` |
| D | RecipeAPI provider term | `"Chicken breast"` |
| E | Local pricing identity | `chicken_breast` (== C, never D) |

`app/domain/ingredient_resolution.py`'s module docstring states this explicitly and is the single place all five are defined together. **D is never read for pricing, and C/E are never fabricated from D.** A generic ingredient can be searchable (D exists, grounded against RecipeAPI's catalogue) while remaining priced as UNKNOWN (no C exists) — this is the intended, tested behavior (§6 below), not a gap.

## 2. Resolution pipeline

Two distinct entry points (`app/agent/ingredient_resolution.py`), matching two distinct questions that must never be conflated:

- **`resolve_pantry_ingredient`** — is a user's typed pantry phrase eligible to enter the pipeline at all, as a canonical id or as a grounded free-text anchor? Runs once per pantry item, in `AgentOrchestrator._init_state`.
- **`resolve_provider_search_term`** — given an identity already accepted into the pipeline, what exact text should reach RecipeAPI.io? Runs lazily, only for identities actually chosen as a search anchor, in `AgentOrchestrator._resolve_outbound_provider_term`.

Order, matching ticket section 9:

1. Local canonical/alias match (existing `ingredient_normalizer.normalize_ingredient_name`, unmodified, now reading the merged built-in + admin vocabulary).
2. Cached provider mapping (`app/integrations/provider_ingredient_cache.py`).
3. Direct natural-language term (`humanize_for_provider`: snake_case/hyphen → spaced text).
4. RecipeAPI `/ingredients` catalogue lookup, only if steps 1-3 didn't already resolve it.
5. Controlled LLM typo/intent correction, only if steps 1-4 all failed.
6. The LLM's proposal is **re-run through steps 1-4 from scratch** — never trusted directly.
7. Proceed if a safe match exists.
8. Otherwise: `UNRESOLVED` or `AMBIGUOUS` — never a silent guess.

## 3. Safe provider-name matching (`select_safe_provider_match`)

Never the first result, never fuzzy/substring. Tiers, in order:

1. Exact / case-insensitive normalized match. Two or more candidates tied here → `AMBIGUOUS`.
2. Deterministic singular/plural variant match (e.g. `"lamb chops"` ↔ `"Lamb chop"`). Two or more tied here → `AMBIGUOUS`.
3. Otherwise → `UNRESOLVED`.

This is what keeps `"lamb chops"` from ever resolving to `"Lamb liver"`, and `"chicken"` from ever resolving to `"Chicken broth"` — neither becomes exactly equal to the query or one of its singular/plural variants, so neither tier accepts them (explicit test coverage: `test_never_matches_a_semantically_different_ingredient`, `test_never_matches_chicken_to_chicken_broth_on_text_overlap_alone`).

### 3.1 The query itself must vary too (the actual "lamb chops" root cause)

Candidate-side singular/plural matching is not enough on its own: it can only compare against candidates a catalogue *query* actually returned. Confirmed live: querying RecipeAPI.io for `"lamb chops"` (plural) returns **zero** candidates — not even the singular `"Lamb chop"` entry that genuinely exists in its catalogue — because the provider's search does not stem plurals server-side.

`resolve_provider_search_term` therefore tries the direct spelling first and, only if that returns no safe match, a bounded number of deterministic singular/plural **query** variants (`singular_plural_query_variants`, typically exactly one extra query — e.g. `"lamb chops"` → `"lamb chop"`). Matching is always evaluated against the *original* identity regardless of which query variant fetched the candidates, so the safe-match tiers are unaffected. This second, query-level fix was found and closed during this ticket's own live test matrix (§7) — the first implementation pass fixed candidate-side matching but still returned zero live results for "lamb chops" until this was added.

Before: `lamb chops` → 0 raw RecipeAPI.io results.
After: `lamb chops` → `"Lamb chop"` → 10 raw RecipeAPI.io results (live-confirmed, §7).

## 4. Provider mapping cache

`app/integrations/provider_ingredient_cache.py`: a bounded (2000-entry), in-memory, 1-hour-TTL cache keyed by the normalized search text, storing either a matched `ProviderIngredient` or an explicit "no match" sentinel (so a genuinely unresolvable term is not re-queried on every request either).

**Chosen over a persistent DB table** because:
- No schema migration risk (additive or otherwise) for what is, by design, a disposable performance optimization — not authoritative data.
- Matches existing codebase precedent (`runtime_ingredient_repository`'s own 30s process-local TTL cache).
- The only cost of a process restart is a cold cache — the exact same catalogue lookups just happen again, at the normal, already-bounded cost.
- It never becomes a second source of truth for pricing or canonical identity (§6) — it caches provider *search terms* only.

## 5. LLM typo/intent correction boundary

`app/integrations/llm_provider.py` adds `propose_ingredient_correction`, a request/response/tool-schema/system-prompt entirely separate from the agent's `decide()` — it cannot influence search strategy, ranking, or recipe content, and is never invoked unless local + catalogue grounding both already failed (ticket section 25: don't call the LLM for ordinary correctly-spelled ingredients).

Its proposal is **never** trusted directly (ticket section 35): `resolve_pantry_ingredient` re-runs the proposed text through the exact same local-then-catalogue grounding steps used for the original text. If that re-grounding fails, the correction is discarded and the term reports `UNRESOLVED` — never a fabricated canonical id, category, or provider term.

Ambiguity is preserved, not narrowed: `"chik"` resolving to two provider candidates at the same tier reports `AMBIGUOUS`, not a guessed cut (test: `test_ambiguous_catalogue_result_never_silently_narrowed`).

No-LLM fallback (ticket section 24): with `llm_provider=None`, ordinary ingredients ("chicken", "mutton") still resolve via local+catalogue grounding alone; only genuine typos ("chiken brest") remain `UNRESOLVED` rather than the pipeline breaking (tests: `test_no_llm_provider_still_resolves_via_local_and_catalogue`, `test_no_llm_provider_leaves_a_true_typo_unresolved_not_broken`).

## 6. Pricing stays separate (DEC-007: unknown price is never zero)

`app/domain/cost_engine.py` was **not modified** — it already priced a recognized-but-missing canonical ingredient as `UNKNOWN`, never `0.0` (verified pre-existing, still true). This ticket adds a distinct, upstream case: an ingredient with **no canonical id at all** (e.g. "mutton" when no admin canonical row exists for it) can now still participate in grounded recipe discovery, but it is carried in `unresolved_ingredients` — a separate, correct bucket, never `missing_ingredients` — and never enters cost calculation at all. Confirmed by `test_pricing_stays_unknown_for_a_provider_grounded_but_locally_unknown_ingredient`: no fabricated canonical id, no entry in any costed bucket.

If an admin later creates `canonical_id=mutton` with a manual price, future requests resolve "mutton" locally (step 1, §2) and price it normally — no code change needed, this already works through the existing runtime ingredient integration.

## 7. Live test matrix (RecipeAPI.io, bounded, manual — `backend/scripts/live_ingredient_resolution_matrix.py`)

Run manually against the live provider; never part of CI/pytest. Final run, 29 live requests total:

| Case | Input | Local resolution | LLM correction | Final provider term | Raw recipe count |
|---|---|---|---|---|---|
| A | chicken | unresolved → catalogue-grounded | — | Chicken | 10 |
| B | lamb | unresolved → catalogue-grounded | — | Lamb | 10 |
| C | lamb chop | `lamb_chops` (exact, singular-fallback) | — | Lamb chop | 10 |
| D | lamb chops | `lamb_chops` (exact) | — | Lamb chop | 10 |
| E | lamb chops + rice | `lamb_chops` (exact); rice unresolved | — | Lamb chop (+ rice unresolved, no generic "Rice" entry exists) | 10 |
| F | chicken breast | `chicken_breast` (exact) | — | Chicken breast | 10 |
| G | chicken breast + rice | `chicken_breast` (exact); rice unresolved | — | Chicken breast | 10 |
| H | mutton | unresolved → catalogue-grounded | — | Mutton | 2 |
| I | chiken | unresolved | chicken | Chicken | 10 |
| J | chiken brest | unresolved | chicken breast → local `chicken_breast` | Chicken breast | 10 |
| K | muton | unresolved | mutton (catalogue-grounded, same as H) | Mutton | 2 |
| L | basmti rice | unresolved | basmati rice → local `basmati_rice` | Basmati rice | 5 |

**Known limitation, not a defect**: bare "rice" (cases E, G) reports `UNRESOLVED`. RecipeAPI.io's catalogue has no single entry literally named `"Rice"` — only qualified varieties ("Arborio rice", "Basmati rice", "Cooked rice", ...). None is an exact or singular/plural match for the bare query, so the safe-matching tiers correctly decline to guess which variety the user means, rather than arbitrarily picking one (same principle as never guessing "chicken" → "chicken broth"). This does not block E/G's other ingredient from anchoring the search — both still returned 10 raw recipes via `lamb chops`/`chicken breast` alone.

## 8. Frontend

`frontend/src/components/IngredientAutocomplete.jsx`: autocomplete is now advisory, not mandatory.

- Enter commits the highlighted suggestion if one is active; otherwise it commits the raw typed text — regardless of whether suggestions are currently showing. This is the actual fix (previously gated on `suggestions.length === 0`).
- Comma also commits free text, matching the existing "type and go" convention.
- New: normalized-duplicate free-text prevention (mirrors the existing canonical-id duplicate prevention) and an 80-character length bound (matching `RecommendRequest`'s own per-ingredient limit).
- No visual/design changes. No dropdown-selection requirement was ever removed — it was never the only path; it is now genuinely optional.

## 9. API / schema

`RecommendRequest.ingredients: list[str]` already accepted arbitrary free text (1-30 items, 1-80 chars each, trimmed) — **no schema change was needed or made**. The gap was entirely in what the backend *did* with an unresolved item (reject the search vs. attempt grounded discovery), not in what the request shape allowed in. `RecommendResponse.pantry_unresolved` already exists and is unchanged; it now legitimately reports fewer terms for the common cases this ticket fixes.

Ambiguous terms (e.g. "chik") are surfaced through the same `pantry_unresolved` list as genuinely-unresolvable terms today — deliberately not a new frontend clarification UI, to keep this ticket's frontend scope to the free-text-entry fix only (ticket section 28's "if backend returns ambiguity" is conditional; internal diagnostics distinguish `AMBIGUOUS` from `UNRESOLVED` via `AgentState.pantry_resolution_log` for logs/tests, per ticket section 26, without a new user-facing surface).

## 10. Zero-result diagnostics (pre-existing, unmodified, re-verified)

`app/agent/observations.py`'s `SearchObservation` already distinguishes `items_returned == 0` (provider itself returned nothing) from `feasible_count_this_attempt == 0` with `items_returned > 0` (provider returned candidates, PantryPilot's deterministic evaluation rejected all of them — with per-candidate `rejection_reasons` and aggregate flags `all_over_budget` / `all_strict_cuisine_mismatch` / `all_max_total_time_exceeded`). This infrastructure was not touched by this ticket and already satisfies ticket section 27.

## 11. Quota / cost impact

- Local exact/alias match: zero catalogue or LLM calls (unchanged from before this ticket).
- A previously-unresolvable generic term (e.g. "chicken", "mutton"): one catalogue call, cached for the rest of the process (default 1h TTL) — not per-request.
- A genuine typo: one (occasionally two, via the singular/plural query fallback) failed catalogue call on the raw text, then one LLM call, then a re-grounding pass that reuses the same cache — so a typo of an already-seen ingredient (e.g. "muton" after "mutton" was already resolved this process) makes zero additional catalogue calls.
- No LLM call is ever made for a term steps 1-4 already resolved (`test_llm_not_called_when_catalogue_already_grounded_it`).
