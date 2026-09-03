# PantryPilot Performance and Reliability Policy

## 1. Purpose

This document defines the mandatory performance and reliability review rules for PantryPilot.

Performance and reliability are acceptance criteria, not optional later reviews.

Every ticket that affects runtime behavior must consider the relevant items in this document.

---

## 2. Current Scale Assumptions

PantryPilot competition MVP assumes:

- low concurrent user volume
- browser-based demo usage
- one bounded recommendation request at a time per user
- local SQLite reads
- one primary external recipe provider
- one LLM agent
- small curated local recipe dataset
- small local reference-price database
- no queue
- no background workers
- no multi-tenant workload
- no high-volume write path

These assumptions are valid only for the competition MVP.

If expected load changes materially, this policy must be reviewed before scaling.

---

## 3. Runtime Performance Targets

Target normal recommendation latency:

- under approximately 8 seconds

Bounded worst-case target:

- under approximately 15 seconds

Local SQLite lookup:

- approximately under 50 ms typical

Frontend feedback:

- visible progress state within approximately 200 ms

Maximum candidate recipes evaluated:

- 20 unique candidates per recommendation

Maximum search strategies:

- default 3

External provider timeout:

- approximately 3–5 seconds per call

No unbounded retries.

No unbounded pagination.

No unbounded candidate evaluation.

---

## 4. Database Review Rules

Every ticket that reads or writes SQLite must review:

- N+1 query risk
- query-inside-loop behavior
- missing indexes
- unbounded result sets
- full table scans
- unnecessary joins
- transaction duration
- lock contention
- duplicate reads
- repeated parsing/deserialization
- unnecessary writes

### N+1

N+1 query patterns are prohibited where a bounded bulk query can be used.

Example to avoid:

```text
for each ingredient:
    query SQLite separately

5. Index Review

Indexes should match actual query paths.

Likely indexed fields include:

ingredient alias
canonical ingredient ID
curated recipe ID
curated recipe ingredient recipe_id
curated recipe ingredient canonical_id
cache key
cache expiry

Do not add indexes merely for appearance.

Each index should support an actual read or integrity requirement.

6. Pagination

External recipe pagination must be bounded.

Rules:

do not automatically crawl pages
pagination is an agent decision
next-page calls require a reason
candidate limit still applies across pages
provider quota/request budget must be respected
7. Agent Loop Performance

The agent must never loop indefinitely.

Controls:

maximum search attempts
maximum tool iterations
maximum candidates
maximum provider requests
bounded corrective retry for malformed tool calls

Stop early when adequate feasible candidates exist.

Do not use additional LLM calls when deterministic tools already provide the required answer.

8. LLM Call Efficiency

Every LLM call adds:

latency
cost
external failure risk

Therefore:

keep tool outputs compact
avoid sending unnecessary full provider payloads
do not send large recipe text unless needed
reuse structured state
avoid calling the model for deterministic calculations
avoid duplicate planning calls
9. RecipeAPI.io Reliability

RecipeAPI.io is an external dependency.

Required controls:

explicit timeout
bounded retry
429 handling
malformed response handling
schema validation
request counting
cache where permitted
no retry storm
no deep pagination
Timeout

A provider timeout must become a typed failure.

The system must not hang indefinitely.

HTTP 429

On rate limit:

do not hammer the provider
mark the condition clearly
use valid cache where available
otherwise return controlled degradation
5xx / Provider Error

Retry only if classified as safe and within the bounded policy.

Do not blindly retry every provider failure.

10. Retry Policy

Retries must be:

bounded
classified
observable
non-recursive
non-amplifying

Examples:

Reasonable Retry

Temporary provider timeout:

one bounded retry if policy permits
Do Not Retry Repeatedly

HTTP 429:

no repeated immediate retry

Malformed provider data:

retrying identical request generally does not fix schema corruption

Invalid user input:

no retry
11. Backoff

If repeated external retry is ever enabled:

use bounded backoff
avoid synchronized retry storms
do not exceed competition latency targets

For current MVP, keep retry behavior minimal.

12. Circuit Breaker

A full circuit-breaker implementation is not required for the competition MVP.

However, provider-health state may temporarily mark RecipeAPI.io unavailable after a clear rate-limit/failure condition within the same request.

If sustained production traffic is introduced later, formal circuit-breaker behavior should be reconsidered.

13. Cache Reliability

Cache exists for:

repeated development queries
latency reduction
quota reduction
demo resilience where permitted

Rules:

cache failure must not corrupt authoritative data
stale cache must not be presented as live
invalid cache payloads must be rejected
duplicate writes should converge safely
cache misses are normal, not errors
14. Application Processing

Review all runtime code for:

unbounded loops
excessive recursion
large in-memory candidate collections
repeated serialization
large JSON payloads
synchronous blocking I/O
unnecessary object copies
unnecessary model calls

Candidate processing must remain bounded.

15. External Payload Size

Provider responses should be reduced to required fields before passing through the full agent loop where practical.

Do not repeatedly send:

long descriptions
unused metadata
unnecessary images
irrelevant fields
massive instruction bodies

if they are not needed for the current decision step.

16. Frontend Reliability

The UI must handle:

loading
slow response
backend error
no feasible recipe
partial/cost-incomplete results
provider degradation
malformed/empty response

The UI must not appear frozen while the agent is working.

17. Progress Events

User-safe progress states may include:

searching recipe sources
checking pantry match
estimating missing-item cost
checking constraints
trying another strategy
comparing feasible options

Progress events must not expose private chain-of-thought.

18. SQLite Reliability

SQLite is acceptable for the competition MVP because:

dataset is small
writes are limited
reads dominate
concurrent load is expected to be low

Review required for:

DB locked errors
corruption/unavailable file
read failure
write transaction failure

The application must fail safely if SQLite is unavailable.

19. Concurrency Assumptions

Current MVP:

low concurrent write activity
mostly request-scoped reads

Potential concurrent write areas:

cache
provider usage metadata

These writes must not create duplicate/corrupt records.

If runtime concurrency increases materially, SQLite and locking assumptions must be revisited.

20. Idempotency

Recommendation execution is primarily read-oriented.

Relevant idempotency concerns:

repeated cache write
repeated import
repeated dataset build
repeated usage counter update

These must produce safe repeatable outcomes.

If future features create external actions, explicit idempotency keys become mandatory.

21. Partial Failure

A single component failure must not cause fabricated results.

Examples:

Missing Price

Result:

cost incomplete

Not:

assume AED 0
Recipe Provider Fails

Result:

use permitted grounded cache if valid
otherwise controlled provider limitation

Not:

generate recipe
LLM Tool Call Invalid

Result:

one bounded correction attempt
then controlled failure

Not:

infinite retry
22. Failure Containment

Failures should remain within module boundaries.

Examples:

provider adapter converts external HTTP failure into typed provider error
price repository converts missing record into explicit no-price result
cost engine handles incomplete price state
API layer maps application error to user-safe response

Do not allow raw vendor exceptions to leak to the frontend.

23. Observability Requirements

Performance/reliability reviews should be supported by logs/metrics such as:

request ID
provider latency
provider status
tool duration
agent attempt count
candidate count
cache hit/miss
DB lookup duration where useful
final recommendation status
timeout/rate-limit event

Do not log hidden chain-of-thought.

24. Failure Taxonomy

At minimum distinguish:

invalid input
provider timeout
provider rate limit
provider malformed response
provider unavailable
DB unavailable
missing price
incomplete cost
agent attempt limit reached
malformed LLM tool call
no feasible recipe
internal unexpected error

This distinction is necessary for correct retry behavior.

25. Performance Regression Rule

If a change materially increases:

provider calls
LLM calls
DB queries
candidate count
payload size
request latency

the PR must explain why.

Unexplained increases should block merge.

26. Performance Test Triggers

Dedicated performance testing is required when a ticket introduces:

bulk processing
larger candidate sets
new provider calls
query-heavy DB operations
high-frequency endpoints
significantly larger payloads
new caching behavior
concurrency-sensitive writes

For current MVP, lightweight timing assertions/benchmarks may be sufficient.

27. Reliability Test Triggers

Explicit failure tests are required for modules involving:

external HTTP
SQLite
LLM tool calling
caching
data import
retry logic
agent stop conditions
28. No Queue Policy

Current MVP has no message queue.

Therefore these are currently NOT APPLICABLE:

at-least-once delivery
poison messages
dead-letter queue
worker concurrency
queue backpressure

If a queue is introduced later, this document must be updated before implementation.

29. No Background Worker Policy

Current MVP has no background worker.

Long-running recommendation work remains within bounded request processing.

If background execution is introduced later, design must address:

retries
duplicate execution
cancellation
state ownership
worker failure
progress persistence

before coding.

30. Provider Failure and Demo Resilience

Competition demo must not depend on uncontrolled external behavior where avoidable.

Before final demo:

verify RecipeAPI.io health
have permitted cached fixtures for regression/demo resilience where allowed
verify local curated source
verify SQLite
verify LLM API
run known-good smoke scenario

Do not present cached data as live if cache is used.

31. Required PR Review Questions

Every meaningful runtime ticket must answer:

Does this add more DB queries?
Does this add provider calls?
Does this add LLM calls?
Is any loop unbounded?
Is pagination bounded?
Are timeouts explicit?
Are retries bounded?
Can partial failure fabricate data?
Can duplicate execution corrupt state?
Does the change affect latency targets?
Are new indexes required?
Is observability sufficient?

If a question is not applicable, explain why.

32. Repeated Reliability Defect Rule

If the same reliability defect occurs twice:

create a structural control such as:

invariant test
timeout wrapper
retry helper
CI check
architecture rule
database constraint

Do not rely only on repeated manual review.

33. Architecture Change Trigger

Revisit this policy before introducing:

second live recipe provider
background workers
queues
high-concurrency writes
user accounts
persistent recommendation history
multi-region deployment
horizontal scaling
streaming/event architecture
real purchasing actions
