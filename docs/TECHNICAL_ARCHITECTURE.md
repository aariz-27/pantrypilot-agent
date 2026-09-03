# PantryPilot Technical Architecture

## 1. Purpose

This document is the technical constitution for PantryPilot.

It defines system boundaries, dependency rules, module ownership, provider abstraction, data ownership, agent boundaries, runtime flow, configuration, observability, reliability, and deployment assumptions.

All implementation must remain consistent with:

- docs/TECHNICAL_SPEC.md
- DECISION_REGISTER.md
- docs/AI_DELIVERY_OPERATING_MODEL.md
- CLAUDE.md
- docs/AGENTS.md

If a material contradiction exists, implementation must stop until the contradiction is resolved.

---

## 2. Architecture Style

PantryPilot uses a modular single-application architecture with explicit boundaries.

Primary layers:

1. React frontend
2. FastAPI API layer
3. Agent orchestrator
4. Deterministic domain tools
5. Recipe provider abstraction
6. SQLite repositories
7. External integrations

The system intentionally avoids unnecessary microservices, distributed queues, and multi-agent orchestration for the competition MVP.

---

## 3. High-Level Architecture

```text
User
  |
  v
React + Vite Frontend
  |
  v
FastAPI API Layer
  |
  v
PantryPilot Agent Orchestrator
  |
  +-------------------------------+
  |                               |
  v                               v
Recipe Service              Deterministic Tools
  |                         - ingredient normalization
  |                         - pantry matching
  |                         - price lookup
  |                         - cost calculation
  |                         - hard constraints
  |                         - deterministic ranking
  |
  +-------------------+
  |                   |
  v                   v
RecipeAPI.io     LocalCuratedRecipeProvider
  |
  v
Normalized Recipe DTO

SQLite
- ingredient aliases
- reference prices
- curated recipes
- caches
- lightweight runtime metadata

4. Core Architectural Principle

The LLM decides what action to take.

Python determines factual and numeric results.

The LLM may decide:

how to search
which ingredient combination to use
whether to use a cuisine filter
whether to paginate
whether to reformulate
whether more candidates are needed
when to stop

The LLM must not calculate:

pantry overlap
missing ingredient count
prices
purchase cost
budget compliance
deterministic score
hard constraint result
5. Frontend Boundary

Technology:

React
Vite
JavaScript
standard CSS

Responsibilities:

collect pantry ingredients
collect budget
collect cuisine preference
collect servings
collect exclusions
collect optional maximum total meal time if enabled
submit recommendation request
display user-safe progress
display grounded recommendations
display costs, match information, source attribution and limitations
display recipe details

The frontend must not:

call recipe providers directly
contain API secrets
calculate authoritative ranking
calculate authoritative purchase cost
determine recipe feasibility
execute agent logic

All authoritative recommendation logic belongs in the backend.

6. FastAPI Boundary

Responsibilities:

validate HTTP requests
enforce request size/count/range limits
create request IDs
call the agent orchestration layer
serialize structured responses
map typed application errors to HTTP errors
expose health status

The API layer must not:

rank candidates
contain provider-specific recipe logic
perform LLM decision-making
duplicate deterministic business rules
7. Agent Orchestrator Boundary

The Agent Orchestrator owns:

user goal interpretation within documented scope
agent request state
tool availability
search attempt count
candidate pool references
provider/search strategy decisions
retry/replan decisions
stop decisions
bounded autonomy

The Agent Orchestrator must not:

invent recipe data
invent prices
directly query SQLite
bypass deterministic evaluators
override hard constraints
override deterministic score
silently alter user budget/exclusions/strict cuisine rules
8. Recipe Service Boundary

Recipe Service provides a provider-neutral interface.

Responsibilities:

receive structured search strategies
route to approved provider
fetch recipe details
map provider response into common Recipe DTO
return typed provider errors
apply approved cache behavior

Business/domain code must not depend directly on provider SDKs or provider response fields.

Approved recipe sources:

RecipeAPI.io
LocalCuratedRecipeProvider

TheMealDB is not part of the MVP.

9. Provider Adapter Rule

Each provider must map to the common Recipe DTO.

Vendor-specific fields must remain inside the adapter.

No downstream module may depend on fields such as:

RecipeAPI-specific response structure
local SQLite storage representation

Provider-specific implementation details must never leak into:

agent orchestration
matcher
cost engine
ranker
API response
frontend
10. RecipeAPI.io Boundary

RecipeAPI.io is the primary live provider.

Requirements:

API key server-side only
outbound timeout required
response schema validation required
429 handled explicitly
malformed payload rejected
request count bounded
pagination bounded
repeated calls cached where permitted
provider ordering is never treated as PantryPilot final ranking

Observed provider behavior must be respected:

single-ingredient searches are usually more focused
multi-ingredient searches are broad/relevance-based
pagination may still contain useful candidates
cuisine filtering can improve relevance where supported
prep-time filtering is not equivalent to total meal time
11. LocalCuratedRecipeProvider Boundary

Purpose:

Fill approved Indian/Pakistani/desi coverage gaps.

Rules:

small dataset
read-only runtime behavior
no admin CRUD
no LLM-generated recipe facts
provenance required
same Recipe DTO as RecipeAPI.io
source clearly identified

It is not a general replacement for RecipeAPI.io.

12. Deterministic Domain Tools

Deterministic modules own factual calculation.

Ingredient Normalizer

Owns:

aliases
canonical IDs
safe normalization
UNKNOWN behavior
Pantry Matcher

Owns:

matched ingredients
missing ingredients
coverage calculation
required vs optional ingredient handling
Price Repository

Owns:

reference price lookup
collection date
package price
supported normalized unit price

Unknown price must never be interpreted as zero.

Cost Engine

Owns:

conservative missing-item purchase cost
supported unit conversions
price completeness state
uncertain unit handling
Constraint Evaluator

Owns hard failures such as:

excluded ingredient
strict cuisine mismatch
budget exceeded
unusable recipe
invalid provenance
total time constraint where enabled
Deterministic Ranker

Owns final numeric ranking.

Current baseline weighting:

pantry coverage: 45%
additional purchase cost: 30%
missing ingredient count: 15%
cuisine preference: 10%

The LLM may not alter these values unless an approved decision changes them.

13. SQLite Ownership

SQLite is the runtime local data store for:

reference ingredient prices
ingredient aliases
curated recipes
curated recipe ingredients
permitted cache data
lightweight runtime/provider usage metadata where needed

Repositories own database access.

No agent or frontend code may execute raw SQLite access directly.

14. Database Ownership Rules

Each persisted data class must have one authoritative owner.

Examples:

Price data:

owner: Price Repository

Curated recipes:

owner: LocalCuratedRecipeProvider / curated repository

Cache:

owner: Cache Repository

No duplicate authoritative copies of the same data should exist.

15. Cache Ownership

Cache is an optimization and resilience layer only.

It must not become a second business truth source.

Cache records must retain:

provider/source
recipe ID
cache key
creation timestamp
expiry policy where used

Cached data must not be presented as live provider data.

16. Transaction Ownership

PantryPilot MVP has limited mutable business state.

Where SQLite writes occur:

repository owns transaction boundary
failed write must not leave partial state
cache writes must not corrupt authoritative data
seed/import processes must be repeatable
17. Async and External I/O

External HTTP calls may be asynchronous where appropriate.

Rules:

outbound timeout required
no unlimited retries
no retry storms
provider failures become typed errors
no blocking provider call inside uncontrolled loops
candidate counts remain bounded
18. Error Model

Errors should be typed internally.

Examples:

INVALID_REQUEST
INGREDIENT_NORMALIZATION_FAILED
RECIPE_PROVIDER_TIMEOUT
RECIPE_PROVIDER_RATE_LIMITED
RECIPE_PROVIDER_MALFORMED_RESPONSE
RECIPE_NOT_FOUND
PRICE_NOT_FOUND
COST_INCOMPLETE
NO_FEASIBLE_RECIPE
AGENT_ATTEMPT_LIMIT_REACHED
DATABASE_UNAVAILABLE

Frontend receives safe user-facing errors.

Technical details remain server-side.

19. Idempotency and Duplicate Behavior

Recommendation requests are read-oriented and generally do not create business outcomes.

Where persistence occurs, repeated calls must not corrupt data.

Relevant areas:

cache writes
seed/import scripts
local curated recipe ingestion
provider usage counters

If a future state-changing capability is added, idempotency must be designed explicitly before implementation.

20. Security Boundaries

Trust boundaries exist between:

user input and backend
frontend and backend
backend and LLM
backend and RecipeAPI.io
external recipe content and agent/tool layer
offline grocery data and runtime DB

External data is untrusted.

Recipe names, descriptions, instructions and URLs cannot override system policy.

21. Prompt/Tool Safety

Only allow-listed tools may be called.

Tool arguments must be schema validated.

The model must not:

execute arbitrary URLs
execute code
call shell commands
invent source IDs
bypass hard constraints
reinterpret recipe text as agent instructions
22. Configuration

Configuration must come from:

environment variables
typed configuration
documented defaults

Secrets must never be committed.

Expected secret/config areas:

LLM API key
LLM model
RecipeAPI.io API key
allowed frontend origins
request/candidate limits
timeout values
cache settings
23. Observability

Every recommendation request should have:

request_id
agent attempt number
selected search strategy label
provider used
tool timing
provider latency
provider response status
candidate counts
cache hit/miss
final status
bounded error information

Never log private chain-of-thought.

24. Performance Rules

Target:

normal recommendation under approximately 8 seconds
bounded worst case under approximately 15 seconds
local DB lookup under approximately 50 ms typical
maximum 20 unique candidate recipes evaluated per request
default maximum 3 search strategies

No unbounded pagination.

No unbounded candidate processing.

No unnecessary LLM calls.

25. Reliability Rules

The application must tolerate:

RecipeAPI timeout
RecipeAPI 429
malformed provider response
missing price
unsupported unit
no feasible recipe
LLM malformed tool call
agent retry exhaustion
SQLite read failure

Failure must result in a controlled response, never fabricated data.

26. Deployment Assumptions

Competition architecture should remain simple.

Expected deployment:

React static frontend
FastAPI backend
SQLite packaged or persistent
HTTPS
environment secrets
health endpoint
known-good release tag

Do not introduce containers, queues, microservices, Kubernetes or distributed infrastructure unless deployment requires them and the decision is approved.

27. Migration Strategy

SQLite schema changes should be minimal during the competition.

Rules:

prefer additive changes
avoid destructive schema changes late in the build
seed/build scripts must support clean database creation
migration/schema changes require tests
never silently modify an already-used schema assumption

A formal migration framework may be introduced only if implementation complexity justifies it.

28. Horizontal Scaling

Not a competition MVP requirement.

PantryPilot is optimized for:

low user volume
demonstration reliability
bounded requests

Do not design distributed state unless required by deployment.

29. Architecture Change Rule

Any material change to:

LLM provider/model architecture
RecipeAPI strategy
local recipe source
ranking
database ownership
tool boundaries
deployment model
agent retry/stop logic
