# PantryPilot Data Integrity Policy

## 1. Purpose

This document defines the mandatory data-integrity rules for PantryPilot.

These rules apply to all modules that create, transform, cache, normalize, import, evaluate, or persist data.

The purpose is to prevent:

- duplicate authoritative records
- silent corruption
- invalid mappings
- stale or ambiguous data becoming authoritative
- partial writes
- incorrect budget decisions
- broken provenance
- inconsistent recipe/source identity

---

## 2. Core Integrity Principles

PantryPilot follows these universal rules:

1. Every persisted state has one authoritative owner.
2. Derived data must not silently become authoritative.
3. Duplicate requests must not create duplicate authoritative outcomes.
4. Failed multi-step writes must roll back atomically.
5. Unknown data must remain unknown.
6. Missing values must never be silently replaced with fabricated values.
7. Provenance must be preserved for recipes and price data.
8. Critical invariants should be enforced in:
   - application validation
   - database constraints where feasible
   - regression tests
9. Schema changes must be deliberate and documented.
10. Data imports must be reproducible.

---

## 3. Authoritative Ownership

### RecipeAPI.io Data

Authoritative source:
RecipeAPI.io

PantryPilot may:
- normalize
- evaluate
- cache where permitted

PantryPilot must not:
- silently rewrite source facts
- invent missing fields
- treat cached copies as more authoritative than source identity

---

### Local Curated Recipes

Authoritative owner:
Local curated recipe repository / SQLite source dataset

Required:
- unique recipe ID
- provenance
- source label
- valid ingredients
- usable instructions

Runtime:
read-only

---

### Ingredient Aliases

Authoritative owner:
Ingredient normalization layer

Rules:
- one alias must not ambiguously map to multiple active canonical IDs
- conflicting mappings must be resolved explicitly
- UNKNOWN is preferable to unsafe over-generalization

---

### Reference Price Data

Authoritative owner:
Price Repository

Required:
- canonical ingredient ID
- positive package price
- source
- collection date

Unknown price must never be interpreted as AED 0.

---

## 4. Critical Invariant Rule

For high-integrity data, where feasible, use:

DB constraint  
+ application validation  
+ regression test

Example:

A reference ingredient price must be greater than zero.

Preferred enforcement:

- DB CHECK constraint where supported
- Python validation
- automated test

---

## 5. Recipe Identity Integrity

A recipe must retain:

- provider/source
- provider_recipe_id or curated recipe ID
- source/provenance metadata

The combination of source + recipe ID defines recipe identity.

The application must not merge two recipes merely because their names are similar.

---

## 6. Recipe Content Integrity

The system must never fabricate missing recipe facts.

Examples:

If provider does not return:
- cook time
- servings
- quantity
- image

then the value remains null/unknown unless a documented deterministic transformation exists.

The LLM may not fill these gaps.

---

## 7. Ingredient Mapping Integrity

Ingredient normalization must avoid unsafe broad mappings.

Examples requiring deliberate handling:

- chicken vs chicken breast
- chicken breast vs chicken wing
- chicken vs carcass
- cheese vs feta
- pasta vs orzo
- bread vs flatbread
- tomato vs canned tomato

If the system cannot safely normalize an ingredient:

return UNKNOWN.

Do not guess merely to improve pantry coverage.

---

## 8. Pantry Match Integrity

Pantry matching must operate on canonical IDs.

Required output:

- matched ingredients
- missing ingredients
- unresolved ingredients
- pantry coverage
- optional ingredients handled separately where defined
- non-food requirements handled separately where defined

The matcher must not silently count unresolved ingredients as matches.

---

## 9. Price Integrity

Price records must satisfy:

- package_price_aed > 0
- canonical_id present
- source present
- collected_at present

If price is unavailable:

- mark price incomplete
- do not assume zero
- do not declare strict budget compliance from incomplete cost data

---

## 10. Currency Precision

AED budget comparison should use Decimal-compatible arithmetic where practical.

Do not rely on binary floating-point when determining:

`estimated_cost <= budget`

if floating-point precision could change the result.

Example:

AED 9.999999 must not accidentally behave differently from the intended AED 10.00 threshold.

---

## 11. Cost Integrity

Cost engine must distinguish:

- known cost
- incomplete cost
- uncertain quantity/unit
- conservative package purchase cost

The engine must never silently convert unsupported units using invented density assumptions.

---

## 12. Ranking Integrity

Ranking inputs must come from deterministic evaluated fields.

The LLM must not invent:

- pantry coverage
- missing count
- cost score
- cuisine score
- final deterministic score

Current ranking weights are governed by approved architecture/decision records.

Changes require approval.

---

## 13. Cache Integrity

Cache is derived data.

Rules:

- cache key must include all relevant search parameters
- provider/source must be retained
- cached recipe identity must be retained
- stale data must not be labelled live
- cache corruption must not modify authoritative recipe/price datasets
- cache may be deleted/rebuilt

Duplicate cache writes should converge safely.

---

## 14. Import Integrity

Offline import/build scripts must be repeatable.

Examples:

- grocery price import
- curated recipe import
- alias import

Running the same import twice must not create uncontrolled duplicate authoritative records.

Use deterministic IDs, uniqueness constraints, replacement strategy, or explicit versioning.

---

## 15. Transaction Boundaries

Use transactions where multiple writes form one logical operation.

Examples:

### Curated Recipe Import

Recipe row + ingredient rows must succeed together.

If ingredient insertion fails:

rollback recipe insertion.

### Dataset Build

Partial failed import must not leave the final production DB in an apparently valid but incomplete state.

Prefer:
- build temporary DB
- validate
- promote only when valid

where practical.

---

## 16. Foreign-Key Integrity

Relationships should be enforced where feasible.

Examples:

`curated_recipe_ingredients.recipe_id`
must reference an existing curated recipe.

No orphan ingredient rows.

---

## 17. Uniqueness

Where applicable enforce uniqueness for:

- curated recipe ID
- canonical ingredient ID
- cache key
- alias where one-to-one mapping is intended

Duplicate authoritative records should fail visibly rather than silently coexist.

---

## 18. Deletion Integrity

Deletion rules must be explicit.

### Cache

May be hard deleted.

### Curated Recipes

Prefer inactive/versioned handling once part of a released dataset.

### Price Dataset

Prefer dataset version replacement/archive rather than silent historical overwrite.

### Canonical Ingredient

Do not delete if referenced without handling dependencies.

---

## 19. Provenance

### Recipe Provenance

Must preserve:
- source/provider
- source recipe ID
- source label where applicable
- source URL where available

### Price Provenance

Must preserve:
- source product name
- source
- source URL where available
- collection date

### Local Curated Recipe Provenance

Must preserve:
- source label
- provenance note
- source URL where applicable

No local curated recipe may exist without provenance.

---

## 20. Time Integrity

System timestamps should use UTC.

Data collection dates should be explicit.

Do not mix ambiguous local timestamps with UTC timestamps in authoritative records.

---

## 21. Negative / Impossible Values

Reject impossible values.

Examples:

- negative price
- zero/negative servings where prohibited
- negative recipe quantity unless semantically valid and explicitly supported
- impossible pagination values
- negative budget
- negative timeout
- invalid ranking weight range

---

## 22. External Data Validation

RecipeAPI.io responses are untrusted until validated.

Required checks include:

- expected schema
- valid recipe ID
- usable name
- ingredient structure
- reasonable list bounds
- usable instructions where required
- valid field types

Malformed provider data must be rejected or degraded safely.

---

## 23. LLM Output Validation

Tool calls from the LLM must be schema validated.

The LLM cannot directly persist authoritative data.

Any LLM-suggested identifier must be checked against:

- known provider results
- canonical ingredient vocabulary
- allowed tool schema

---

## 24. Duplicate Business Outcome Prevention

Current MVP is mostly read-oriented.

Potential duplicate effects still include:

- duplicate cache records
- duplicate import rows
- duplicate curated records
- duplicate usage counters

These must be safely bounded.

If later PantryPilot adds any state-changing external action, explicit idempotency becomes mandatory before implementation.

---

## 25. Concurrency

Current MVP assumes low concurrent write volume.

SQLite is acceptable under that assumption.

If write concurrency grows materially, re-evaluate:

- locking
- transaction duration
- contention
- lost updates
- SQLite suitability

This re-evaluation must occur before scaling the architecture.

---

## 26. Migration Integrity

Schema changes must not casually modify already-used assumptions.

Rules:

- prefer additive changes
- document destructive changes
- update tests
- update source datasets/build scripts
- verify clean DB creation
- verify existing DB compatibility where applicable

---

## 27. Recovery

Where practical, authoritative local data must be reconstructable from repository-controlled source data.

Examples:

- aliases
- curated recipes
- normalized grocery source
- schema/build scripts

Do not make manual production-only DB edits the only source of truth.

---

## 28. Data Integrity Review Requirement

Every ticket affecting:

- database
- schema
- recipe DTO
- ingredient normalization
- pricing
- cache
- import
- cost calculation
- ranking
- provider mapping

must explicitly answer:

1. What authoritative data is affected?
2. What invariants apply?
3. Can duplicates occur?
4. Can partial failure corrupt state?
5. Are DB constraints needed?
6. Are regression tests required?
7. Can the data be reconstructed?
8. Is provenance preserved?

---

## 29. Defect Rule

If a data-integrity defect is confirmed:

1. identify the immediate defect
2. identify the violated invariant
3. identify all alternate paths with the same risk
4. add a regression test
5. add a structural control where feasible
6. record the finding in the remediation register
