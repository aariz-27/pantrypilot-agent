# PantryPilot Data Architecture

## 1. Purpose

This document defines PantryPilot's canonical data entities, ownership, source of truth, persistence rules, lineage, sensitivity, retention, constraints, and concurrency expectations.

It complements:

- docs/TECHNICAL_ARCHITECTURE.md
- docs/SYSTEM_CONTEXT.md
- docs/TECHNICAL_SPEC.md
- DECISION_REGISTER.md

---

## 2. Data Architecture Principles

PantryPilot follows these rules:

1. Every persisted data class has one authoritative owner.
2. External provider payloads are never used directly outside adapters.
3. Canonical internal models are provider-neutral.
4. Derived data must be reproducible from authoritative inputs where practical.
5. Cache is never treated as independent business truth.
6. Critical invariants should be enforced by:
   - application validation
   - database constraints where feasible
   - regression tests
7. Unknown data must remain unknown rather than being silently fabricated.
8. Recipe provenance must be preserved.
9. Pricing provenance and collection date must be preserved.
10. User pantry/preferences should not be persisted beyond what is necessary for the MVP.

---

## 3. Canonical Data Domains

PantryPilot has five main data domains:

1. Recipe data
2. Ingredient canonicalization data
3. Price/reference data
4. Cache/provider metadata
5. Request/session state

---

## 4. Recipe Data

### 4.1 Canonical Recipe

The internal Recipe DTO is the authoritative application representation of a recipe after provider mapping.

Representative structure:

```text
Recipe
- provider
- provider_recipe_id
- name
- cuisine
- category
- image_url
- ingredients[]
- instructions
- source_url
- servings
- prep_time_minutes
- cook_time_minutes
- cached
- provenance/source metadata

4.2 RecipeIngredient

Representative fields:

RecipeIngredient
- raw_name
- canonical_id
- quantity
- unit
- measure_raw
- optional
- non_food_requirement
4.3 Source Ownership

External RecipeAPI.io recipe records:

authoritative source: RecipeAPI.io
PantryPilot stores normalized/cached copies only where permitted

Local curated recipes:

authoritative source: local curated recipe store
provenance required
read-only runtime behavior
4.4 Mutability

External recipe records:

immutable within a request
cache may expire/refresh

Local curated recipes:

effectively immutable during competition runtime
changes occur only through governed dataset update
5. Ingredient Canonicalization Data
5.1 Canonical Ingredient

Representative fields:

CanonicalIngredient
- canonical_id
- display_name
- category
- active
5.2 Ingredient Alias

Representative fields:

IngredientAlias
- alias
- canonical_id
- source
- confidence/manual_status
5.3 Ownership

Canonical vocabulary owner:

Ingredient Normalization module

Alias storage owner:

alias repository / SQLite or approved static data file
5.4 Rules
one canonical ID may have many aliases
one alias should resolve to one approved canonical ID
unresolved names become UNKNOWN
aliases must not silently map ambiguous specialized ingredients to overly broad parents

Examples requiring controlled handling:

chicken vs chicken breast/thigh/wing/carcass
bread vs specific bread types
cheese vs feta/kasar/etc.
pasta vs orzo/macaroni
tomato vs canned/diced tomato
6. Price Reference Data
6.1 IngredientPrice

Representative fields:

IngredientPrice
- canonical_id
- display_name
- source_product_name
- package_quantity
- package_unit
- package_price_aed
- normalized_price_per_unit
- normalized_unit
- source_name
- source_url
- collected_at
- active
6.2 Ownership

Authoritative runtime owner:

Price Repository

Acquisition source:

offline Apify grocery acquisition
6.3 Rules
price must be positive
source and collection date required
unknown price is never zero
budget feasibility uses conservative package purchase cost
price data is reference data, not live data
duplicate active canonical price records must be avoided unless explicitly versioned
6.4 Versioning

Price records should retain collection date.

If refreshed later:

old records may be archived/versioned
active/reference record must be explicit
historical overwrite without trace should be avoided
7. Local Curated Recipe Data
7.1 CuratedRecipe

Representative fields:

CuratedRecipe
- id
- name
- cuisine
- category
- servings
- prep_time_minutes
- cook_time_minutes
- instructions
- image_url
- source_label
- source_url
- provenance_note
- active
7.2 CuratedRecipeIngredient

Representative fields:

CuratedRecipeIngredient
- id
- recipe_id
- raw_name
- canonical_id
- quantity
- unit
- optional
7.3 Rules
recipe ID unique
provenance required
active flag explicit
no LLM-generated recipe content
runtime read-only
same Recipe DTO mapping as RecipeAPI.io
ingredient rows must reference valid recipe IDs
8. Cache Data
8.1 Recipe Cache

Representative fields:

RecipeCacheEntry
- cache_key
- provider
- cache_type
- payload_json
- created_at
- expires_at
- source_request_fingerprint
8.2 Ownership

Cache Repository owns cache persistence.

8.3 Rules
cache is derived data
cache can be deleted/rebuilt
cache must not become an independent authoritative recipe source
provider/source identity must be retained
stale cache must not be presented as live data
cache key must include relevant normalized search parameters and page
9. Provider Usage Metadata

Optional lightweight metadata may include:

ProviderUsage
- provider
- request_date
- request_count
- last_status
- last_error

Purpose:

quota awareness
observability
demo reliability

This is operational metadata, not business data.

10. Request / Agent State

Agent state is primarily in-memory/request-scoped.

Representative fields:

AgentRequestState
- request_id
- pantry
- budget_aed
- cuisine_preference
- cuisine_strict
- servings
- max_total_time_minutes
- excluded_ingredients
- search_attempts
- searched_terms
- candidate_pool
- evaluated_candidates
- best_feasible
Persistence Policy

Default:

do not persist full request state

May log:

request_id
high-level strategy
counts
timing
status

Do not log private chain-of-thought.

11. Authoritative vs Derived Records
Authoritative
canonical ingredient vocabulary
ingredient aliases
local curated recipes
active reference price records
configuration/decision-controlled data
External Authoritative Source
RecipeAPI.io recipe data
Derived
normalized Recipe DTO from external provider
cache entries
candidate evaluation
ranking score
pantry coverage
cost estimates
agent observations

Derived data should be reproducible from authoritative/source data where practical.

12. Immutable Data

Treat as immutable within runtime:

source recipe identity
provider recipe ID
local curated recipe provenance
historical collection date
request ID
final logged decision outcome for a completed request if persisted

Do not mutate provenance history silently.

13. Soft vs Hard Delete
Hard Delete Allowed
expired cache entries
temporary development fixtures
invalid seed data before release
Prefer Soft/Versioned Handling
curated recipes once released
canonical ingredient definitions
price dataset versions

For the competition MVP, dataset updates may be managed through controlled rebuilds, but source history should remain in Git.

14. Retention
User Inputs

Default:

request/session scoped
no long-term storage required
Logs

Retain only what is necessary for:

debugging
performance
provider failures
competition demonstration

Avoid storing full raw user inputs unless required.

Cache

Retain according to provider terms and configured TTL.

Price Dataset

Retain current release dataset in repository/package and provenance metadata.

15. PII Classification

Current MVP collects no intended PII.

Pantry ingredients, cuisine preference, and budget are not treated as identity data.

Still:

avoid unnecessary persistence
do not combine with external identifiers
revise classification if accounts/user profiles are added later
16. Sensitive Fields

Sensitive:

LLM API key
RecipeAPI.io API key
deployment credentials

These must not be stored in application database.

Use:

environment variables
secret stores
17. Encryption Requirements
In Transit

External/runtime HTTP traffic should use HTTPS.

At Rest

SQLite data contains no high-sensitivity user data in the MVP.

Special database encryption is not required for the competition MVP.

Secrets remain outside SQLite.

If persistent user/account data is added later, this decision must be revisited.

18. Timestamp Rules

Use explicit timestamps.

Recommended:

UTC for system timestamps
ISO 8601 representation at API/log boundaries

Examples:

collected_at
created_at
expires_at

Do not use ambiguous local timestamps for authoritative operational data.

19. Numeric Precision
Prices / Currency

Use Decimal-compatible handling in Python for authoritative AED calculations where practical.

Do not rely on binary floating-point for exact budget comparisons if this can cause threshold errors.

SQLite storage should use a consistent representation.

Coverage / Ranking

Floating-point is acceptable for normalized ranking scores because these are derived decision metrics, not financial ledger values.

20. Database Constraints

Where feasible, enforce:

ingredient_prices
canonical_id NOT NULL
package_price_aed > 0
collected_at NOT NULL
active constrained to boolean-like value
ingredient_aliases
alias unique where appropriate
canonical_id required
curated_recipes
id primary key
name required
source_label required
provenance_note required
active constrained
curated_recipe_ingredients
recipe_id foreign key
raw_name required
cache
cache_key primary/unique
provider required
created_at required
21. Indexing Expectations

At minimum consider indexes for:

ingredient_prices(canonical_id)
ingredient_aliases(alias)
curated_recipe_ingredients(recipe_id)
curated_recipe_ingredients(canonical_id)
recipe_cache(provider, cache_key)
recipe_cache(expires_at)

Final indexes should be validated against actual queries.

22. Concurrency

PantryPilot MVP has low write concurrency.

Most runtime operations are reads.

Potential concurrent writes:

cache writes
provider usage counters

Rules:

cache writes must tolerate duplicate attempts
unique keys should prevent duplicate authoritative cache entries
retry behavior must not corrupt data

If heavier write concurrency is introduced later, SQLite suitability must be re-evaluated.

23. Transaction Rules

Use transactions for multi-step writes where partial persistence would be invalid.

Examples:

curated recipe + ingredient import
price dataset rebuild/import
cache write/update where required

Failure must roll back the logical unit.

24. Seed / Build Strategy

Database creation should be reproducible from governed source data.

Expected flow:

aliases / curated recipe source / normalized grocery dataset
        ↓
build scripts
        ↓
SQLite database
        ↓
validation checks
        ↓
packaged competition DB

The final runtime database should not depend on manual ad-hoc editing.

25. Data Quality Gates
Price Data
positive prices
source present
collection date present
duplicate canonical IDs resolved
representative common ingredient coverage
Curated Recipes
provenance present
recipe ID unique
valid ingredient rows
usable instructions
cuisine metadata present
no generated content
Aliases
no conflicting duplicate mapping
high-use aliases regression tested
26. Lineage

For important local data, retain lineage:

Price

raw source product
→ normalized canonical ingredient
→ selected reference record
→ SQLite IngredientPrice

Curated Recipe

approved recipe source/manual record
→ curated dataset
→ SQLite
→ common Recipe DTO

RecipeAPI.io

provider response
→ provider adapter
→ common Recipe DTO
→ candidate evaluation

27. Reconstruction

Derived state should be reconstructable where practical.

Reconstructable:

cache
ranking
candidate evaluation
coverage
cost estimate
runtime DB from source datasets/build scripts

Do not make an unrecoverable derived record authoritative.

28. Schema Change Rule

Material changes to:

Recipe DTO
ingredient canonical model
price schema
curated recipe schema
cache schema

require:

approved ticket
architecture/data impact review
updated tests
updated documentation
migration/rebuild plan where necessary

Claude Code must not silently change these schemas.
