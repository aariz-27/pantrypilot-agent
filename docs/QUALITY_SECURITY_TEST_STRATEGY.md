# PantryPilot Quality, Security and Test Strategy

## 1. Purpose

This document defines the mandatory testing and quality expectations for PantryPilot.

Testing must prove system invariants, not only happy-path function outputs.

Every confirmed defect should receive a regression test unless technically impossible.

---

## 2. Test Principles

1. Deterministic business rules require automated tests.
2. Provider boundaries require contract-style tests.
3. Security-sensitive behavior requires explicit negative testing.
4. Agent behavior requires scenario tests.
5. Bug fixes require regression coverage.
6. Database behavior should use real SQLite tests where DB semantics matter.
7. Tests must verify failure behavior, not only success.
8. Tests must remain bounded and reproducible.
9. Live provider tests should be minimal and controlled.
10. CI should rely primarily on mocks/fixtures for deterministic repeatability.

---

## 3. Test Layers

### Unit Tests

Required for:

- ingredient normalization
- alias handling
- pantry matching
- optional ingredient behavior
- non-food requirement classification
- price lookup
- unit conversion
- cost calculation
- budget comparison
- hard constraints
- ranking
- total-time calculation
- retry/stop helpers

### Integration Tests

Required for:

- RecipeAPI adapter
- LocalCuratedRecipeProvider
- Recipe Service
- SQLite repositories
- cache behavior
- FastAPI routes
- agent tool integration

### Real Database Tests

Use actual SQLite where behavior depends on:

- uniqueness
- foreign keys
- transactions
- cache persistence
- curated recipe relationships
- price records
- import/build scripts

### Contract Tests

Required for:

- RecipeProvider interface
- Recipe DTO mapping
- tool input/output schemas
- FastAPI request/response shapes

### Negative Tests

Required for:

- malformed user input
- malformed provider response
- invalid tool call
- unknown ingredient
- missing price
- unsupported unit
- strict cuisine mismatch
- budget exceeded
- provider timeout
- 429
- invalid recipe identity
- prompt-like text in external data

### Security Tests

Required where applicable for:

- prompt/tool abuse
- secret exposure
- unsafe rendering
- injection
- oversized input
- arbitrary URL attempts
- malformed tool arguments
- provider content injection
- rate abuse boundaries

### Performance Tests

Required only when a change affects:

- candidate volume
- DB query volume
- provider calls
- payload size
- LLM calls
- cache behavior

Lightweight timing/benchmark checks are enough for the competition MVP unless a specific bottleneck appears.

---

## 4. Tenant-Isolation Tests

Current PantryPilot MVP has:

- no accounts
- no tenants
- no multi-user persisted state

Therefore tenant-isolation testing is:

NOT APPLICABLE to the current MVP.

This must be revisited before implementing accounts, tenants, or persisted user ownership.

---

## 5. Concurrency Tests

Current concurrency risk is limited.

Concurrency tests are relevant for:

- cache writes
- duplicate import/build execution
- provider usage counters where persisted

If later mutable user state or external actions are added, concurrency testing becomes mandatory.

---

## 6. Idempotency Tests

Current relevant idempotency areas:

- repeated cache write
- repeated dataset import
- repeated curated recipe import
- repeatable DB build

Tests should verify that repeated execution does not create duplicate authoritative records.

---

## 7. Migration Tests

If schema changes are introduced:

test:

- clean database creation
- forward schema update where applicable
- constraints
- compatibility with existing fixtures
- rebuild behavior
- failure behavior

Do not casually rewrite a migration that has already been used.

---

## 8. Regression Test Rule

Every confirmed defect must result in:

- a regression test

unless technically impossible.

Any exception must document:

- why it cannot be automated
- manual verification method
- residual risk

---

## 9. Provider Testing Strategy

### RecipeAPI.io

Use:

- mocked payloads for CI
- recorded fixtures for regression
- limited live smoke tests

Test:

- successful search
- focused single-ingredient query
- broad multi-ingredient query
- pagination
- cuisine filter
- detail lookup
- timeout
- 429
- malformed payload
- empty result
- optional ingredient fields
- unusual units
- non-food requirement data

Do not consume live quota for every test run.

### LocalCuratedRecipeProvider

Test:

- search
- exact lookup
- cuisine routing
- empty result
- provenance
- malformed local record
- inactive recipe behavior
- DTO equivalence with RecipeAPI.io mapping

---

## 10. Deterministic Core Tests

### Ingredient Normalizer

Test:

- exact canonical match
- alias
- plural
- capitalization
- safe descriptor removal
- capsicum → bell_pepper
- ambiguous specialized ingredient
- UNKNOWN
- cached normalization

### Pantry Matcher

Test:

- full match
- partial match
- no match
- optional ingredient
- unresolved ingredient
- non-food requirement
- parent/child equivalence boundaries

### Price Repository

Test:

- known price
- unknown price
- invalid price
- source/date required
- active/inactive record
- bulk lookup

### Cost Engine

Test:

- package price
- supported mass conversion
- supported volume conversion
- count
- unknown price
- unsupported unit
- strict budget with incomplete cost
- Decimal comparison

### Constraint Evaluator

Test:

- excluded ingredient
- strict cuisine
- budget exceeded
- total-time exceeded
- incomplete recipe
- invalid provenance
- unknown total time when time is strict

### Ranker

Test:

- documented weights
- stable deterministic result
- lower cost preferred where appropriate
- fewer missing ingredients preferred
- cuisine preference
- infeasible candidate excluded

---

## 11. Agent Behavior Tests

The agent must be tested as a decision system.

### A01 Search Reformulation

Initial search produces weak candidates.

Agent chooses a materially different search strategy.

Pass condition:
Python does not hardcode the exact next query.

### A02 Pagination Decision

Current query is relevant but first page candidates are infeasible.

Agent chooses next page.

### A03 Budget Replanning

Attractive candidate exceeds budget.

Agent searches for a different feasible option.

### A04 Stop Early

Three strong feasible candidates exist.

Agent stops instead of wasting calls.

### A05 Retry Exhaustion

Maximum search attempts reached.

Agent returns grounded alternatives and stops.

### A06 Hallucination Prevention

Agent attempts to reference nonexistent recipe/provider ID.

Tool validation rejects it.

### A07 Strict Regional Routing

Strict Indian/Pakistani/desi request uses local curated source.

No unrelated cuisine is presented as satisfying strict intent.

### A08 Provider Failure

RecipeAPI.io unavailable.

System uses valid cache if available or returns controlled limitation.

No fabricated recipe.

---

## 12. Mandatory Regression Fixture Pack

Maintain approximately 15–20 fixed scenarios.

Include at least:

1. chicken/rice/onion/garlic
2. egg/bread/cheese
3. lentil/rice/onion
4. pasta/tomato/cheese
5. high pantry match within budget
6. top overlap over budget
7. strict cuisine mismatch
8. soft cuisine preference
9. missing price
10. unsupported measure
11. optional ingredient
12. non-food requirement
13. no feasible recipe
14. provider timeout
15. provider 429
16. malformed provider payload
17. focused search then pagination
18. weak broad search then reformulation
19. strict desi/local source
20. max total time if feature remains enabled

Expected behavior should be stable even if live provider ranking changes.

Use recorded/mock provider data for CI.

---

## 13. API Tests

At minimum test:

### GET /api/health

- healthy
- DB unavailable
- degraded provider status

### GET /api/ingredients/suggest

- valid search
- empty result
- input limits

### POST /api/recommend

- valid request
- invalid request
- budget
- exclusions
- strict cuisine
- provider failure
- no feasible match
- partial/cost incomplete
- bounded retries

### GET /api/recipes/{provider}/{id}

- valid
- unknown ID
- malformed provider
- unavailable source

---

## 14. Frontend Tests

Minimum critical smoke coverage:

- pantry entry
- budget input
- cuisine input
- exclusions
- submit
- loading/progress
- recommendations
- error state
- no-feasible state
- source attribution
- cost display
- recipe detail

The frontend must never render raw HTML from provider data.

---

## 15. Security Test Areas

Where technically applicable:

- long/oversized ingredient input
- script-like user input
- prompt injection in ingredient text
- prompt injection inside recipe content
- malformed URL
- tool argument tampering
- unexpected provider fields
- secrets absent from frontend bundle
- CORS behavior
- API request limits
- unsafe HTML rendering
- dependency scanning

---

## 16. Failure Testing

Every external dependency integration must test:

- timeout
- connection failure
- malformed response
- rate limit
- empty response

The application must return controlled errors.

No external failure may result in fabricated recipe data.

---

## 17. Escape-Path Testing

When a ticket implements a control, tests should consider whether another path bypasses it.

Examples:

If strict budget is enforced in one evaluation path:
- verify every recommendation path uses the same evaluator

If source provenance is enforced:
- verify local and live provider routes both enforce it

If candidate count is bounded:
- verify pagination cannot bypass the global limit

---

## 18. Test Evidence

Each implementation ticket should record:

- test command
- test result
- relevant test files
- any manual verification
- known gaps

Where useful, store evidence under:

`evidence/<TICKET-ID>/`

Do not store redundant noise.

---

## 19. CI Expectations

CI should eventually run:

- formatter/linter
- type checks
- backend tests
- frontend build/tests
- governance validation
- architecture boundary checks
- security scans where practical

Live RecipeAPI.io tests should not run on every CI build.

---

## 20. Definition of Test Complete

A ticket is not test-complete merely because existing tests pass.

Test completion requires:

- acceptance criteria covered
- relevant negative path covered
- relevant failure path covered
- regression coverage added for defects
- architecture invariant tested where practical
- no unexplained skipped tests
- known gaps documented

---

## 21. Bug Fix Test Rule

Every bug fix must answer:

1. What failed?
2. What invariant was violated?
3. Why did existing tests miss it?
4. Which regression test now proves the fix?
5. Is there another path with the same defect?
6. Can a structural guard prevent recurrence?

---

## 22. Competition Release Test Gate

Before final submission:

- all P0 tests pass
- all critical agentic proof tests pass
- security-critical tests pass
- provider smoke test passes
- SQLite clean build passes
- frontend build passes
- end-to-end demo scenario passes
- no unresolved critical/high-severity remediation finding remains without explicit accepted risk
