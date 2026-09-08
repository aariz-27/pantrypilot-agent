// Deterministic, frontend-side recompute for the "I have this" feature
// (ticket section 2, PR #15 review; extended to unresolved ingredients
// in the PR #15 correction pass, 2026-09-08, Priority 3). This module
// never calls the backend/LLM -- it only re-derives pantry match %,
// matched/missing/unresolved lists, and estimated cost from data the
// /api/recommend response already returned, using the exact same
// arithmetic the backend uses (pantry_coverage = matched / (matched +
// missing + unresolved); cost = sum of remaining missing ingredients'
// already-known per-ingredient costs, never fabricated, never coerced
// to zero when incomplete).
//
// Two independent "I have this" sources feed the same matched-display
// list:
// - A missing row with a real canonical_id (extraCanonicalIds) --
//   promoted into a trusted match, exactly as before.
// - An unresolved row (extraUnresolvedIdentityKeys, keyed by the
//   backend's deterministic raw-text identity_key, never a
//   canonical_id) -- the user's own confirmed raw pantry state. It is
//   still never assigned a canonical_id, never promoted into the
//   taxonomy, and never given a fabricated price; it only stops
//   contributing cost/match UNCERTAINTY for this card (ticket
//   Priority 3: "this remains user-confirmed raw pantry state, not
//   taxonomy/pricing truth").
//
// Priority 4 (PR #15 correction pass, 2026-09-08): the backend now also
// returns additional_options -- already-evaluated, already-feasible
// candidates ranked below the top 3 (never a hard-rejected candidate;
// those stay in closest_alternatives, untouched here). When a
// confirmation changes any card's coverage/cost, the FULL local pool
// (recommendations + additional_options) is recomputed, then RE-RANKED
// with the exact frozen formula (./ranking.js, a port of
// backend/app/domain/ranker.py) and re-split into a new top 3 / rest --
// entirely client-side, zero Claude/RecipeAPI.io calls. A reserve
// candidate ranked #5 can become #1 this way.

import { rerankCards } from './ranking'

const MAX_FINAL_RECOMMENDATIONS = 3 // mirrors backend/app/agent/state.py

// PR #15 fifth correction pass (2026-09-08, product decision): mirrors
// AgentOrchestrator._finalize's partition exactly -- recommendations
// and additional_options are built EXCLUSIVELY from anchor-matching
// cards; a non-anchor card never pads a recommendations slot (that
// prior-pass behavior was reversed -- "fewer genuinely relevant
// recommendations" is now preferred over padding with an unrelated
// alternative). Since the backend already guarantees
// recommendations/additional_options only ever contain anchor-matching
// cards, this filter is defensive/idempotent by construction -- it
// never needs to MOVE a non-anchor card anywhere (contains_active_anchor
// is immutable per card; confirming ingredients only changes
// coverage/cost, never which canonical ingredients a recipe contains),
// so a non-anchor card simply never entered this pool to begin with.
// No-op when no card in the pool carries any anchor information at all
// (nothing to discriminate by); otherwise strictly requires
// contains_active_anchor === true.
function filterToAnchorOnly(cards) {
  const hasAnyAnchorInfo = cards.some((c) => c.contains_active_anchor === true || c.contains_active_anchor === false)
  if (!hasAnyAnchorInfo) return cards
  return cards.filter((c) => c.contains_active_anchor === true)
}

function round2(value) {
  return Math.round(value * 100) / 100
}

// Applies confirmed-owned ingredients (both trusted canonical matches
// and confirmed-but-unresolved raw text) to one recipe card, moving
// matching rows into "matched" and recomputing coverage/cost. Returns
// the SAME object (referential equality preserved) when nothing on
// this card is affected, so callers can cheaply skip re-rendering
// unaffected cards.
export function applyExtraPantryToCard(card, extraCanonicalIds, extraUnresolvedIdentityKeys) {
  const hasCanonical = extraCanonicalIds && extraCanonicalIds.size > 0
  const hasUnresolved = extraUnresolvedIdentityKeys && extraUnresolvedIdentityKeys.size > 0
  if (!card || (!hasCanonical && !hasUnresolved)) return card

  const stillMissing = []
  const newlyMatchedNames = []
  for (const row of card.missing_ingredients) {
    if (hasCanonical && row.canonical_id && extraCanonicalIds.has(row.canonical_id)) {
      newlyMatchedNames.push(row.display_name)
    } else {
      stillMissing.push(row)
    }
  }

  const stillUnresolved = []
  for (const row of card.unresolved_ingredients) {
    if (hasUnresolved && extraUnresolvedIdentityKeys.has(row.identity_key)) {
      newlyMatchedNames.push(row.display_name)
    } else {
      stillUnresolved.push(row)
    }
  }

  if (newlyMatchedNames.length === 0) return card

  const matchedSet = new Set(card.matched_ingredients)
  for (const name of newlyMatchedNames) matchedSet.add(name)
  const matched_ingredients = Array.from(matchedSet)

  const totalRequired = card.matched_ingredients.length + card.missing_ingredients.length + card.unresolved_ingredients.length
  const pantry_coverage = totalRequired === 0 ? card.pantry_coverage : matched_ingredients.length / totalRequired

  // Post-review fix (2026-09-08): stillMissing.every(...) on an EMPTY
  // array is vacuously true, so once every recognized missing
  // ingredient was checked off, cost was wrongly marked complete (AED
  // 0) even when an unresolved required ingredient (unknown price,
  // never promoted into a trusted match) was still present. An
  // unresolved required ingredient's cost is never known, so
  // completeness must also require there to be none left -- now
  // "none left" means none still unconfirmed (stillUnresolved), since
  // a CONFIRMED-owned unresolved ingredient no longer needs a purchase
  // price at all (Priority 3).
  const allRemainingComplete = stillUnresolved.length === 0 && stillMissing.every((row) => row.price_complete)
  const estimated_additional_spend_aed = allRemainingComplete
    ? round2(stillMissing.reduce((sum, row) => sum + (row.estimated_cost_aed ?? 0), 0))
    : null

  return {
    ...card,
    matched_ingredients,
    missing_ingredients: stillMissing,
    unresolved_ingredients: stillUnresolved,
    pantry_coverage,
    price_complete: allRemainingComplete,
    estimated_additional_spend_aed,
  }
}

// Applies the same confirmed-owned sets across every card in a full
// /api/recommend response (ticket: "update all currently displayed
// recipe cards, not only the card clicked" / "same unresolved raw
// ingredient updates across multiple cards where identity matching is
// safe").
export function applyExtraPantryToResponse(response, extraCanonicalIds, extraUnresolvedIdentityKeys, rankingConstraints = {}) {
  const hasCanonical = extraCanonicalIds && extraCanonicalIds.size > 0
  const hasUnresolved = extraUnresolvedIdentityKeys && extraUnresolvedIdentityKeys.size > 0
  if (!response || (!hasCanonical && !hasUnresolved)) return response

  const recomputedRecommendations = response.recommendations.map((card) =>
    applyExtraPantryToCard(card, extraCanonicalIds, extraUnresolvedIdentityKeys),
  )
  const recomputedAdditional = (response.additional_options ?? []).map((card) =>
    applyExtraPantryToCard(card, extraCanonicalIds, extraUnresolvedIdentityKeys),
  )

  // Priority 4: rerank the COMBINED pool (never mixing in
  // closest_alternatives -- those are a structurally separate,
  // non-anchor fallback section and can never become a
  // recommendation/additional_option). A reserve candidate whose
  // coverage improved can now outrank an original top-3 card.
  // PR #15 fifth correction pass: filtered to anchor-only AFTER
  // ranking (defensive; the backend already guarantees this pool is
  // anchor-only), so the local "I have this" recompute can never
  // reintroduce the padding behavior this pass removed.
  const rerankedPool = rerankCards([...recomputedRecommendations, ...recomputedAdditional], rankingConstraints)
  const anchorOnlyPool = filterToAnchorOnly(rerankedPool)
  const recommendations = anchorOnlyPool.slice(0, MAX_FINAL_RECOMMENDATIONS)
  const additionalOptions = anchorOnlyPool.slice(MAX_FINAL_RECOMMENDATIONS)

  return {
    ...response,
    recommendations,
    additional_options: additionalOptions,
    closest_alternatives: response.closest_alternatives.map((card) =>
      applyExtraPantryToCard(card, extraCanonicalIds, extraUnresolvedIdentityKeys),
    ),
  }
}
