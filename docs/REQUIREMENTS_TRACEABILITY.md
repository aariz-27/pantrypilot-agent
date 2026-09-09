# PantryPilot Requirements Traceability

## 1. Purpose

This document maps project requirements to implementation work, tests, pull requests, and evidence.

It must answer:

- Why does this code exist?
- Which requirement does this ticket implement?
- Which tests prove that requirement?
- Which PR delivered it?
- What is the current status?

This document is a traceability index, not a replacement for the Master Blueprint or `TECHNICAL_SPEC.md`.

---

## 2. Authoritative Requirement Sources

Primary requirement sources:

- `docs/PantryPilot_Master_Project_Blueprint_v3.1_REVISED_FINAL.docx`
- `docs/TECHNICAL_SPEC.md`
- `DECISION_REGISTER.md`
- `docs/TECHNICAL_ARCHITECTURE.md`

Where a requirement is architectural rather than product-functional, reference the relevant architecture or decision document.

---

## 3. Traceability Model

Requirement  
↓  
Ticket  
↓  
Module / Service  
↓  
Tests  
↓  
Pull Request  
↓  
Evidence  
↓  
Status

---

## 4. Status Values

Use:

- `NOT_STARTED`
- `DESIGNED`
- `IN_IMPLEMENTATION`
- `IN_REVIEW`
- `IMPLEMENTED`
- `VERIFIED`
- `BLOCKED`
- `DEFERRED`

`IMPLEMENTED` means code exists.

`VERIFIED` means the implementation has passed required review/testing.

---

## 5. Functional Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| FR-01 | User can add/edit/remove pantry ingredients | Master Blueprint | M01 Frontend | TBD | TBD | TBD | TBD | DESIGNED |
| FR-02 | User can enter optional AED budget | Master Blueprint | M01, M02 | TBD | TBD | TBD | TBD | DESIGNED |
| FR-03 | User can select cuisine preference and strict/soft mode | Master Blueprint | M01, M02, M09 | TBD | TBD | TBD | TBD | DESIGNED |
| FR-04 | User can enter servings | Master Blueprint | M01, M02 | TBD | TBD | TBD | TBD | DESIGNED |
| FR-05 | User can specify excluded ingredients | Master Blueprint | M01, M02, M09 | TBD | TBD | TBD | TBD | DESIGNED |
| FR-06 | Backend normalizes raw ingredients to canonical IDs | Master Blueprint | Ingredient Normalizer | PP-001 | backend/tests/unit/test_ingredient_normalizer.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-07 | Agent selects recipe search strategy through tool calls | Master Blueprint | M03 Agent Orchestrator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_first_search_with_three_feasible_candidates_stops`, `test_llm_can_choose_a_pantry_derived_anchor_and_it_executes_correctly`) | #11 | 5170c03 (merge); 98497ad (impl head) — `AgentOrchestrator._decide_next_action`/`_handle_search` (`backend/app/agent/orchestrator.py`), structured tool calling via `AnthropicLLMProvider` (`backend/app/integrations/llm_provider.py`) | IMPLEMENTED |
| FR-08 | RecipeAPI.io is primary live provider | Revised architecture / DEC-002 | Recipe Service / RecipeAPI adapter | PP-002 | backend/tests/unit/test_recipeapi_io_adapter.py | #3 | 7cde50c (merge); 521a482 (impl head); live-verified (4 requests) | IMPLEMENTED |
| FR-09 | All recipe sources map to one internal Recipe DTO | Revised architecture | Recipe Service / adapters | PP-002 | backend/tests/unit/test_provider_contract.py | #3 | 7cde50c (merge); 521a482 (impl head) | IMPLEMENTED |
| FR-10 | Pantry overlap and missing ingredients are deterministic | Master Blueprint | Pantry Matcher | PP-001 | backend/tests/unit/test_pantry_matcher.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-11 | Reference prices are read from local SQLite | Master Blueprint | Price Repository | PP-003 | backend/tests/unit/test_price_repository.py | #5 | 39fbe62 (merge); aff4bd4 (impl head) | IMPLEMENTED |
| FR-12 | Missing-item purchase cost is deterministic | Master Blueprint | Cost Engine | PP-003 | backend/tests/unit/test_cost_engine.py | #5 | 39fbe62 (merge); aff4bd4 (impl head) | IMPLEMENTED |
| FR-13 | Hard constraints are enforced before ranking | Master Blueprint | Constraint Evaluator | PP-001 | backend/tests/unit/test_constraint_evaluator.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-14 | Feasible candidates are ranked deterministically | Master Blueprint | Ranker | PP-001 | backend/tests/unit/test_ranker.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-15 | Agent changes search strategy when needed within bounds | Master Blueprint | M03 Agent Orchestrator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_zero_results_leads_to_a_different_strategy`, `test_all_candidates_over_budget_triggers_new_strategy`, `test_strict_cuisine_mismatch_triggers_new_strategy`, `test_identical_search_strategy_cannot_be_repeated_without_transient_failure`) | #11 | 5170c03 (merge); 98497ad (impl head) — `AgentOrchestrator._handle_search` distinct-strategy-signature enforcement | IMPLEMENTED |
| FR-16 | Regional desi/Indian/Pakistani routing uses approved local curated source | DEC-003 | LocalCuratedRecipeProvider | PP-002 | backend/tests/unit/test_local_curated_provider.py | #3 | 7cde50c (merge); 521a482 (impl head) — foundation only; zero production recipe data; DEC-012 remains OPEN | IN_IMPLEMENTATION |
| FR-17 | Agent stops after configured bounds and returns grounded alternatives | Master Blueprint | M03 Agent Orchestrator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_candidate_cap_of_20_enforced`, `test_search_attempt_cap_enforced_even_if_model_requests_more`, `test_provider_unavailable_with_no_fallback_terminates_safely`, `test_grounded_provenance_survives_through_orchestration`) | #11, #12 | 5170c03 (merge #11); cecaf2c (merge #12) — `AgentOrchestrator._finalize`/`_closest_alternatives` (`backend/app/agent/orchestrator.py`) | IMPLEMENTED |
| FR-18 | UI explains why recommendations were selected | Master Blueprint | M01 Frontend | TBD | TBD | TBD | TBD | DESIGNED |
| FR-19 | No LLM-created recipe may be displayed | Master Blueprint / DEC-001 | Cross-cutting | PP-002 | backend/tests/unit/test_recipe_mapping.py | #3 | 7cde50c (merge); 521a482 (impl head) — provenance/identity guard (`require_usable_identity`) implemented and tested; no LLM/display path exists yet to actually attempt fabrication | IN_IMPLEMENTATION |
| FR-20 | Final recipe content must trace to approved source identity | Master Blueprint | Recipe Service / API response | PP-002 | backend/tests/unit/test_recipe_mapping.py | #3 | 7cde50c (merge); 521a482 (impl head) | IMPLEMENTED |
| FR-21 | External provider usage is bounded, cached where permitted, and observable | Master Blueprint | Recipe Service / Observability | TBD | TBD | TBD | TBD | DESIGNED |
| FR-22 | Pantry (recognized and raw/unknown entries) persists locally across reload, without duplicates | Module F Ticket 5.1 | Frontend | Module F | `frontend/src/utils/storage.test.js`, `frontend/src/domain/pantryItems.test.js` | TBD | `frontend/src/utils/storage.js` (versioned localStorage), `frontend/src/domain/pantryItems.js` (dedupe) | IMPLEMENTED |
| FR-23 | Search-form preferences (servings, max time, difficulty, cuisine) persist locally across reload; budget never persists | Module F Ticket 5.2 | Frontend | Module F | `frontend/src/App.test.jsx` (includes explicit budget-not-persisted regression case) | TBD | `frontend/src/App.jsx` `loadInitialFormState`/`PREFS_STORAGE_KEY` | IMPLEMENTED |
| FR-24 | Recent-search history (bounded, rerun, clear) | Module F Ticket 5.3 | Frontend | Module F | `frontend/src/hooks/useRecentSearches.test.jsx` | TBD | `frontend/src/hooks/useRecentSearches.js` — capped at 8 entries; stores only search parameters, never full LLM/provider responses | IMPLEMENTED |
| FR-25 | Saved/favorite recipes (minimal, provider-grounded fields only) | Module F Ticket 5.4 | Frontend | Module F | `frontend/src/hooks/useSavedRecipes.test.jsx` | TBD | `frontend/src/hooks/useSavedRecipes.js` — stores provider recipe ID/source/title/image URL/source URL/timestamp only; no generated content | IMPLEMENTED |
| FR-26 | All local state (pantry, prefs, history, saved recipes) is clearable without developer tools | Module F Ticket 5.5 | Frontend | Module F | `frontend/src/App.test.jsx` | TBD | `frontend/src/components/LocalDataPanel.jsx` | IMPLEMENTED |

---

## 6. Architecture Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| AR-01 | Single-agent architecture | DEC-005 | M03 | Module D | N/A (structural/architectural — one `AgentOrchestrator` class owns the full decision loop; no sub-agent, multi-agent, or agent-to-agent handoff exists anywhere in `backend/app/agent/`) | #11 | 5170c03 (merge); 98497ad (impl head) | IMPLEMENTED |
| AR-02 | Deterministic calculations remain outside LLM | DEC-006 | Core deterministic modules | PP-001 | backend/tests/unit/ (normalizer, matcher, constraint evaluator, ranker) | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| AR-03 | Provider-specific fields must not leak beyond adapter boundary | TECHNICAL_ARCHITECTURE | Recipe Service / adapters | PP-002 | backend/tests/unit/test_recipeapi_io_adapter.py (`test_provider_specific_raw_fields_do_not_leak_into_recipe`) | #3 | 7cde50c (merge); 521a482 (impl head) | IMPLEMENTED |
| AR-04 | RecipeAPI.io is primary live source | DEC-002 | RecipeAPI adapter | PP-002 | backend/tests/unit/test_recipeapi_io_adapter.py | #3 | 7cde50c (merge); 521a482 (impl head) | IMPLEMENTED |
| AR-05 | Local curated provider handles approved regional gaps | DEC-003 | LocalCuratedRecipeProvider | PP-002 | backend/tests/unit/test_local_curated_provider.py | #3 | 7cde50c (merge); 521a482 (impl head) — foundation only; DEC-012 remains OPEN | IN_IMPLEMENTATION |
| AR-06 | TheMealDB is excluded from MVP | DEC-004 | Cross-cutting | N/A | N/A | N/A | N/A | VERIFIED |
| AR-07 | SQLite owns local reference/runtime data | DEC-008 | Repositories / DB | PP-003 | backend/tests/unit/test_price_repository.py | #5 | 39fbe62 (merge); aff4bd4 (impl head) | IMPLEMENTED |
| AR-08 | Frontend contains no authoritative business calculations | TECHNICAL_ARCHITECTURE | M01 | TBD | TBD | TBD | TBD | DESIGNED |
| AR-09 | API layer contains no ranking/provider-specific business logic | TECHNICAL_ARCHITECTURE | M02 | TBD | TBD | TBD | TBD | DESIGNED |
| AR-10 | External provider calls have explicit timeout and bounded retry | PERFORMANCE_RELIABILITY_POLICY | RecipeAPI adapter | TBD | TBD | TBD | TBD | DESIGNED |
| AR-11 | Candidate and search attempt counts remain bounded | TECHNICAL_ARCHITECTURE | M03 / Recipe Service | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_candidate_cap_of_20_enforced`, `test_search_attempt_cap_enforced_even_if_model_requests_more`); backend/tests/agent/test_observations_and_state.py (`test_bounds_constants_match_technical_spec`, `test_state_capacity_and_exhaustion_helpers`) | #11 | 5170c03 (merge); 98497ad (impl head) — `MAX_SEARCH_ATTEMPTS=3`, `MAX_EVALUATED_CANDIDATES=20` (`backend/app/agent/state.py`), enforced independently of LLM output in `AgentOrchestrator.run` | IMPLEMENTED |
| AR-12 | Unknown price is never treated as zero | DATA_INTEGRITY_POLICY | Price Repository / Cost Engine | PP-001, PP-003 | backend/tests/unit/test_constraint_evaluator.py, test_ranker.py, test_price_repository.py, test_cost_engine.py | #1, #5 | acb5278 (merge, PP-001 foundation); 39fbe62 (merge, PP-003) now enforces this against a real `PriceRepository`/`CostEngine` and the real LuLu dataset, not just the frozen contract | IMPLEMENTED |
| AR-13 | Recipe provenance is preserved | DATA_ARCHITECTURE | Recipe Service / local provider | PP-001 | backend/tests/unit/test_constraint_evaluator.py | #1 | acb5278 (merge); 5865b79 (impl head) — provenance-validation foundation only; no Recipe Service/provider adapters yet | IN_IMPLEMENTATION |
| AR-14 | No secrets are exposed to frontend or Git | Threat Model / Security Matrix | Config / deployment | TBD | TBD | TBD | TBD | DESIGNED |
| AR-15 | Raw external provider content is treated as untrusted data | Threat Model | Agent / adapters / frontend | Module D (agent side only; frontend not started) | backend/tests/agent/test_observations_and_state.py (`test_untrusted_recipe_text_is_confined_to_the_observation_data_block`); backend/tests/agent/test_orchestrator_scenarios.py (`test_malicious_recipe_title_does_not_change_agent_policy_or_flow`) | #11 | 5170c03 (merge); 98497ad (impl head) — `AnthropicLLMProvider._user_content` labels the observation payload `UNTRUSTED_STRUCTURED_DATA` and keeps it isolated from `system_policy` (`backend/app/integrations/llm_provider.py`) | IN_IMPLEMENTATION |

---

## 7. Security Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| SEC-01 | Recipe/user text cannot override system policy | THREAT_MODEL | Agent Orchestrator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_malicious_recipe_title_does_not_change_agent_policy_or_flow`); backend/tests/agent/test_observations_and_state.py (`test_untrusted_recipe_text_is_confined_to_the_observation_data_block`) | #11 | 5170c03 (merge); 98497ad (impl head) — `SYSTEM_POLICY` is a fixed developer-authored constant (`backend/app/agent/policy.py`) never concatenated with request/observation data | IMPLEMENTED |
| SEC-02 | Only allow-listed tools may execute | CLAUDE.md / Threat Model | Agent Orchestrator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_unsupported_action_type_is_rejected`); backend/tests/agent/test_actions.py (`test_agent_action_rejects_unknown_action_type`) | #11 | 5170c03 (merge); 98497ad (impl head) — `ActionType` is a closed enum (SEARCH/PAGINATE/RETRY/STOP) (`backend/app/agent/actions.py`); `AnthropicLLMProvider` forces `tool_choice` to the single named tool (`backend/app/integrations/llm_provider.py`) | IMPLEMENTED |
| SEC-03 | Tool arguments are schema validated | API Integration Standards | Agent / tools | Module D | backend/tests/agent/test_actions.py (`test_search_args_rejects_extra_fields`, `test_search_args_rejects_empty_anchor_list`, `test_search_args_caps_anchor_list_length`, `test_agent_action_rejects_top_level_extra_fields`); backend/tests/agent/test_orchestrator_scenarios.py (`test_malformed_arguments_get_one_corrective_retry`, `test_second_malformed_response_is_a_typed_failure`) | #11 | 5170c03 (merge); 98497ad (impl head) — pydantic-validated `AgentAction`/`SearchArgs` (`backend/app/agent/actions.py`), one bounded corrective retry on validation failure (`AgentOrchestrator._decide_next_action`) | IMPLEMENTED |
| SEC-04 | Arbitrary outbound URLs are prohibited | THREAT_MODEL | Recipe adapter / tools | PP-002, Module E | `backend/app/integrations/recipeapi_io.py` (`BASE_URL` is a fixed constant, never built from user/provider input); `frontend/src/utils/safeUrl.test.js` | PP-002, #15 | Reconfirmed by the Module F 4.9 security review; no arbitrary-URL-fetch path found anywhere server-side | IMPLEMENTED |
| SEC-05 | API keys remain server-side | Security Matrix | Config / deployment | PP-002 | `backend/app/config.py` (`SecretStr` fields); `.gitignore` excludes `.env`/`.env.local`; `backend/.env.example` placeholder-only | PP-002 | Reconfirmed by the Module F 4.5 security review; no key found in frontend bundle or API responses | IMPLEMENTED |
| SEC-06 | Provider content is safely rendered | Threat Model | Frontend | Module E | `frontend/src/utils/safeUrl.js` + `.test.js`; `frontend/src/components/RecipeDetail.jsx` (image/source URL rendering, `rel="noreferrer"`); no `dangerouslySetInnerHTML` anywhere in `frontend/src/` | #15 | Reconfirmed by the Module F 4.9 security review | IMPLEMENTED |
| SEC-07 | Public request inputs are bounded | API Integration Standards | API Layer | PP-001, PP-002 | `backend/tests/integration/test_recommend_endpoint.py` (bounds/negative cases) | PP-001, PP-002 | Reconfirmed by the Module F 4.1 security review; complemented (not replaced) by SEC-09's request-body-size cap | IMPLEMENTED |
| SEC-08 | Provider responses are schema validated | Threat Model | RecipeAPI adapter | TBD | Malformed response tests | TBD | TBD | DESIGNED |
| SEC-09 | Request body size is bounded | Module F Ticket 4.2 | API Layer | Module F | `backend/tests/unit/test_request_size_limit_middleware.py`, `backend/tests/integration/test_request_size_limit_endpoint.py` | TBD | `backend/app/middleware/request_size_limit.py` — 16 KiB cap enforced before Pydantic validation or any agent/provider call, streaming-enforced against actual bytes received (not just a spoofable `Content-Length` header) | IMPLEMENTED |
| SEC-10 | Public endpoints are rate-limited per client | Module F Ticket 4.3 | API Layer | Module F | `backend/tests/integration/test_rate_limiting.py` | TBD | `backend/app/rate_limit.py` — `slowapi`, in-memory, per-client-IP; `/api/recommend` 10/min, `/api/ingredients/suggest` 60/min, both env-configurable; 429 responses use the existing error-envelope shape and occur before any provider/LLM call | IMPLEMENTED |

---

## 8. Reliability / Performance Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| REL-01 | Normal recommendation target under ~8 s | Performance Policy | Cross-cutting | TBD | Timing evidence | TBD | TBD | DESIGNED |
| REL-02 | Worst-case bounded path under ~15 s target | Performance Policy | M03 / provider layer | Module D | None — no automated test asserts wall-clock latency; `scripts/live_smoke_full_pipeline.py` is a manual, one-off live run with no timing assertion | TBD | Structural bound exists (max 3 search attempts x 20 candidates, `backend/app/agent/state.py`), which bounds worst-case *work* but the ~15s *latency* target itself has not been measured or tested | DESIGNED |
| REL-03 | External provider timeout required | Performance Policy | RecipeAPI adapter | TBD | Timeout test | TBD | TBD | DESIGNED |
| REL-04 | 429 does not create retry storm | Performance Policy | RecipeAPI adapter | TBD | 429 test | TBD | TBD | DESIGNED |
| REL-05 | No unbounded pagination | Performance Policy | M03 / Recipe Service | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_paginate_continues_the_same_strategy`, `test_search_attempt_cap_enforced_even_if_model_requests_more`) | #11 | 5170c03 (merge); 98497ad (impl head) — `AgentOrchestrator._require_paginatable`/`_next_page_strategy`: paginate is only permitted after a prior successful `has_more` attempt, and each paginate call still counts against `MAX_SEARCH_ATTEMPTS` | IMPLEMENTED |
| REL-06 | Maximum 20 unique candidates per request | Technical Architecture | M03 / evaluator | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_candidate_cap_of_20_enforced`); backend/tests/agent/test_observations_and_state.py (`test_bounds_constants_match_technical_spec`) | #11 | 5170c03 (merge); 98497ad (impl head) — `MAX_EVALUATED_CANDIDATES = 20` (`backend/app/agent/state.py`) | IMPLEMENTED |
| REL-07 | Maximum 3 default search strategies | Technical Architecture | M03 | Module D | backend/tests/agent/test_orchestrator_scenarios.py (`test_search_attempt_cap_enforced_even_if_model_requests_more`); backend/tests/agent/test_observations_and_state.py (`test_bounds_constants_match_technical_spec`) | #11 | 5170c03 (merge); 98497ad (impl head) — `MAX_SEARCH_ATTEMPTS = 3` (`backend/app/agent/state.py`) | IMPLEMENTED |
| REL-08 | Cache failure does not corrupt authoritative data | Performance Policy | Cache Repository | TBD | Cache failure tests | TBD | TBD | DESIGNED |

---

## 9. Test Requirement Traceability

The following mandatory scenarios must eventually link to concrete tests and tickets:

| Test ID | Scenario | Requirement(s) | Ticket | Test File | PR | Status |
|---|---|---|---|---|---|---|
| Q01 | High pantry match within budget | FR-10, FR-12, FR-14 | TBD | TBD | TBD | DESIGNED |
| Q02 | Highest overlap exceeds budget | FR-13, FR-14 | TBD | TBD | TBD | DESIGNED |
| Q03 | Weak first query causes reformulation | FR-15, AR-01 | TBD | TBD | TBD | DESIGNED |
| Q04 | RecipeAPI failure handled safely | REL-03, REL-04 | TBD | TBD | TBD | DESIGNED |
| Q05 | No feasible result returns grounded alternatives | FR-17, FR-19 | TBD | TBD | TBD | DESIGNED |
| Q06 | Capsicum alias normalizes correctly | FR-06 | TBD | TBD | TBD | DESIGNED |
| Q07 | Missing grocery price is not zero | AR-12 | TBD | TBD | TBD | DESIGNED |
| Q08 | Strict cuisine mismatch rejected | FR-03, FR-13 | TBD | TBD | TBD | DESIGNED |
| Q09 | Provider timeout controlled | REL-03 | TBD | TBD | TBD | DESIGNED |
| Q10 | Provider 429 controlled | REL-04 | TBD | TBD | TBD | DESIGNED |
| Q11 | LLM-created recipe blocked | FR-19 | TBD | TBD | TBD | DESIGNED |
| Q12 | Prompt injection in recipe content ignored | SEC-01 | TBD | TBD | TBD | DESIGNED |
| Q13 | Malformed provider payload rejected | SEC-08 | TBD | TBD | TBD | DESIGNED |
| Q14 | Unsupported unit handled explicitly | FR-12 | TBD | TBD | TBD | DESIGNED |
| Q15 | Very long/malicious user input rejected | SEC-07 | TBD | TBD | TBD | DESIGNED |

---

## 10. Updating This Document

When a ticket is authorized:

- populate `Ticket`
- populate planned tests if known

When a PR opens:

- populate `PR`
- update status to `IN_REVIEW`

After merge:

- record evidence
- update status to `IMPLEMENTED`

After independent verification:

- update to `VERIFIED` where appropriate

Do not mark requirements `VERIFIED` merely because Claude reports success.

---

## 11. Source-of-Truth Rule

This file is authoritative for requirement-to-delivery traceability.

However:

- Master Blueprint / `TECHNICAL_SPEC.md` remain authoritative for requirement meaning
- GitHub remains authoritative for actual PR/merge state
- test files/CI remain authoritative for actual test execution
- `CURRENT_STATUS.md` remains authoritative for current project phase

Do not duplicate or contradict those sources.
