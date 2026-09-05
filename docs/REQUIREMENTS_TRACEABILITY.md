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
| FR-07 | Agent selects recipe search strategy through tool calls | Master Blueprint | M03 Agent Orchestrator | TBD | TBD | TBD | TBD | DESIGNED |
| FR-08 | RecipeAPI.io is primary live provider | Revised architecture / DEC-002 | Recipe Service / RecipeAPI adapter | TBD | TBD | TBD | TBD | DESIGNED |
| FR-09 | All recipe sources map to one internal Recipe DTO | Revised architecture | Recipe Service / adapters | TBD | TBD | TBD | TBD | DESIGNED |
| FR-10 | Pantry overlap and missing ingredients are deterministic | Master Blueprint | Pantry Matcher | PP-001 | backend/tests/unit/test_pantry_matcher.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-11 | Reference prices are read from local SQLite | Master Blueprint | Price Repository | TBD | TBD | TBD | TBD | DESIGNED |
| FR-12 | Missing-item purchase cost is deterministic | Master Blueprint | Cost Engine | PP-001 | backend/tests/unit/test_ranker.py | #1 | acb5278 (merge); 5865b79 (impl head) — foundation/input-shape only: `CostEvaluation` typed plug-point + ranker/constraint-evaluator integration; real cost calculation deferred to the Price Repository/Cost Engine ticket | IN_IMPLEMENTATION |
| FR-13 | Hard constraints are enforced before ranking | Master Blueprint | Constraint Evaluator | PP-001 | backend/tests/unit/test_constraint_evaluator.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-14 | Feasible candidates are ranked deterministically | Master Blueprint | Ranker | PP-001 | backend/tests/unit/test_ranker.py | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| FR-15 | Agent changes search strategy when needed within bounds | Master Blueprint | M03 Agent Orchestrator | TBD | TBD | TBD | TBD | DESIGNED |
| FR-16 | Regional desi/Indian/Pakistani routing uses approved local curated source | DEC-003 | LocalCuratedRecipeProvider | TBD | TBD | TBD | TBD | DESIGNED |
| FR-17 | Agent stops after configured bounds and returns grounded alternatives | Master Blueprint | M03 Agent Orchestrator | TBD | TBD | TBD | TBD | DESIGNED |
| FR-18 | UI explains why recommendations were selected | Master Blueprint | M01 Frontend | TBD | TBD | TBD | TBD | DESIGNED |
| FR-19 | No LLM-created recipe may be displayed | Master Blueprint / DEC-001 | Cross-cutting | TBD | TBD | TBD | TBD | DESIGNED |
| FR-20 | Final recipe content must trace to approved source identity | Master Blueprint | Recipe Service / API response | TBD | TBD | TBD | TBD | DESIGNED |
| FR-21 | External provider usage is bounded, cached where permitted, and observable | Master Blueprint | Recipe Service / Observability | TBD | TBD | TBD | TBD | DESIGNED |

---

## 6. Architecture Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| AR-01 | Single-agent architecture | DEC-005 | M03 | TBD | TBD | TBD | TBD | DESIGNED |
| AR-02 | Deterministic calculations remain outside LLM | DEC-006 | Core deterministic modules | PP-001 | backend/tests/unit/ (normalizer, matcher, constraint evaluator, ranker) | #1 | acb5278 (merge); 5865b79 (impl head) | IMPLEMENTED |
| AR-03 | Provider-specific fields must not leak beyond adapter boundary | TECHNICAL_ARCHITECTURE | Recipe Service / adapters | TBD | TBD | TBD | TBD | DESIGNED |
| AR-04 | RecipeAPI.io is primary live source | DEC-002 | RecipeAPI adapter | TBD | TBD | TBD | TBD | DESIGNED |
| AR-05 | Local curated provider handles approved regional gaps | DEC-003 | LocalCuratedRecipeProvider | TBD | TBD | TBD | TBD | DESIGNED |
| AR-06 | TheMealDB is excluded from MVP | DEC-004 | Cross-cutting | N/A | N/A | N/A | N/A | VERIFIED |
| AR-07 | SQLite owns local reference/runtime data | DEC-008 | Repositories / DB | TBD | TBD | TBD | TBD | DESIGNED |
| AR-08 | Frontend contains no authoritative business calculations | TECHNICAL_ARCHITECTURE | M01 | TBD | TBD | TBD | TBD | DESIGNED |
| AR-09 | API layer contains no ranking/provider-specific business logic | TECHNICAL_ARCHITECTURE | M02 | TBD | TBD | TBD | TBD | DESIGNED |
| AR-10 | External provider calls have explicit timeout and bounded retry | PERFORMANCE_RELIABILITY_POLICY | RecipeAPI adapter | TBD | TBD | TBD | TBD | DESIGNED |
| AR-11 | Candidate and search attempt counts remain bounded | TECHNICAL_ARCHITECTURE | M03 / Recipe Service | TBD | TBD | TBD | TBD | DESIGNED |
| AR-12 | Unknown price is never treated as zero | DATA_INTEGRITY_POLICY | Price Repository / Cost Engine | PP-001 | backend/tests/unit/test_constraint_evaluator.py, test_ranker.py | #1 | acb5278 (merge); 5865b79 (impl head) — enforced at the `CostEvaluation`/constraint-evaluator/ranker boundary; no live Price Repository yet | IMPLEMENTED |
| AR-13 | Recipe provenance is preserved | DATA_ARCHITECTURE | Recipe Service / local provider | PP-001 | backend/tests/unit/test_constraint_evaluator.py | #1 | acb5278 (merge); 5865b79 (impl head) — provenance-validation foundation only; no Recipe Service/provider adapters yet | IMPLEMENTED |
| AR-14 | No secrets are exposed to frontend or Git | Threat Model / Security Matrix | Config / deployment | TBD | TBD | TBD | TBD | DESIGNED |
| AR-15 | Raw external provider content is treated as untrusted data | Threat Model | Agent / adapters / frontend | TBD | TBD | TBD | TBD | DESIGNED |

---

## 7. Security Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| SEC-01 | Recipe/user text cannot override system policy | THREAT_MODEL | Agent Orchestrator | TBD | Prompt injection tests | TBD | TBD | DESIGNED |
| SEC-02 | Only allow-listed tools may execute | CLAUDE.md / Threat Model | Agent Orchestrator | TBD | Tool abuse tests | TBD | TBD | DESIGNED |
| SEC-03 | Tool arguments are schema validated | API Integration Standards | Agent / tools | TBD | Malformed tool tests | TBD | TBD | DESIGNED |
| SEC-04 | Arbitrary outbound URLs are prohibited | THREAT_MODEL | Recipe adapter / tools | TBD | SSRF-negative tests | TBD | TBD | DESIGNED |
| SEC-05 | API keys remain server-side | Security Matrix | Config / deployment | TBD | Secret/bundle review | TBD | TBD | DESIGNED |
| SEC-06 | Provider content is safely rendered | Threat Model | Frontend | TBD | XSS rendering tests | TBD | TBD | DESIGNED |
| SEC-07 | Public request inputs are bounded | API Integration Standards | API Layer | TBD | Negative API tests | TBD | TBD | DESIGNED |
| SEC-08 | Provider responses are schema validated | Threat Model | RecipeAPI adapter | TBD | Malformed response tests | TBD | TBD | DESIGNED |

---

## 8. Reliability / Performance Requirements Traceability

| Requirement ID | Requirement Summary | Source | Planned Module(s) | Ticket | Tests | PR | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| REL-01 | Normal recommendation target under ~8 s | Performance Policy | Cross-cutting | TBD | Timing evidence | TBD | TBD | DESIGNED |
| REL-02 | Worst-case bounded path under ~15 s target | Performance Policy | M03 / provider layer | TBD | Bounded scenario tests | TBD | TBD | DESIGNED |
| REL-03 | External provider timeout required | Performance Policy | RecipeAPI adapter | TBD | Timeout test | TBD | TBD | DESIGNED |
| REL-04 | 429 does not create retry storm | Performance Policy | RecipeAPI adapter | TBD | 429 test | TBD | TBD | DESIGNED |
| REL-05 | No unbounded pagination | Performance Policy | M03 / Recipe Service | TBD | Pagination-bound tests | TBD | TBD | DESIGNED |
| REL-06 | Maximum 20 unique candidates per request | Technical Architecture | M03 / evaluator | TBD | Candidate-bound test | TBD | TBD | DESIGNED |
| REL-07 | Maximum 3 default search strategies | Technical Architecture | M03 | TBD | Retry exhaustion test | TBD | TBD | DESIGNED |
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
