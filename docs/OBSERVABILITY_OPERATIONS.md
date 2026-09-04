# PantryPilot Observability and Operations

## 1. Purpose

This document defines the minimum observability and operational controls for PantryPilot.

The goal is to make failures diagnosable without introducing unnecessary infrastructure.

PantryPilot competition MVP should provide enough evidence to answer:

- What request failed?
- Which dependency failed?
- How long did the request take?
- Which provider/search path was used?
- Was cache used?
- How many candidates were evaluated?
- Did the agent hit its limits?
- Was the failure retryable?
- Was the result grounded?

---

## 2. Current MVP Context

PantryPilot currently uses:

- React + Vite frontend
- FastAPI backend
- SQLite
- RecipeAPI.io
- local curated recipe provider
- LLM provider
- deterministic matching/cost/ranking logic

The MVP does not require:

- distributed tracing platform
- message queue monitoring
- Kubernetes observability
- multi-region telemetry
- SIEM integration
- enterprise APM

Use lightweight structured logging and operational checks unless deployment needs expand.

---

## 3. Observability Principles

Observability should be:

- structured
- bounded
- useful
- privacy-conscious
- secret-safe
- correlated by request
- implementation-independent where practical

Do not log large raw payloads merely because they are available.

---

## 4. Request ID

Every public recommendation request must receive a unique `request_id`.

The same request ID should appear in:

- API response
- backend logs
- provider-call logs
- agent execution logs
- error logs
- performance timing records

This is the primary correlation mechanism for the MVP.

---

## 5. Structured Logging

Backend logs should use structured key/value data where practical.

Representative fields:

- timestamp
- level
- request_id
- component
- operation
- provider
- duration_ms
- outcome
- error_code
- retryable
- candidate_count
- search_attempt
- cache_status

Do not rely only on free-form log messages.

---

## 6. Log Levels

Use consistent severity:

### DEBUG

Detailed development-only diagnostics.

Examples:

- normalized aliases
- internal scoring inputs
- provider mapping details

Do not enable excessive DEBUG logging in public deployment.

### INFO

Normal operational events.

Examples:

- request started
- request completed
- provider call completed
- cache hit/miss
- agent attempt completed

### WARNING

Recoverable abnormal behavior.

Examples:

- provider timeout followed by fallback
- partial price coverage
- retryable provider failure
- bounded attempt exhaustion

### ERROR

Request or capability failure requiring investigation.

Examples:

- malformed provider response
- database failure
- invalid internal state
- uncaught provider adapter error

### CRITICAL

Severe systemic condition.

Examples:

- secret exposure detected
- database corruption
- primary business path unusable
- security control bypass

---

## 7. Secret Logging Policy

Never log:

- RecipeAPI.io API key
- LLM API key
- Authorization header
- `.env` contents
- deployment secrets
- full credential-bearing URLs
- private system prompts
- hidden chain-of-thought

If an error object contains a secret-bearing field, sanitize it before logging.

---

## 8. User Input Logging

Pantry ingredient input is relatively low sensitivity, but logs should still be minimal.

Prefer recording:

- ingredient count
- exclusion count
- budget-present flag
- cuisine mode
- servings
- normalized count

Avoid logging full user text unless needed during bounded debugging.

Do not create unnecessary persistent user profiles.

---

## 9. Provider Call Logging

For RecipeAPI.io calls, record:

- request_id
- provider
- operation
- search attempt number
- page number where applicable
- duration_ms
- response category
- number of mapped results
- rate-limit status where observable
- retry count
- cache interaction

Do not log provider credentials.

---

## 10. LLM / Agent Logging

For agent execution, record high-level operational evidence:

- request_id
- model/provider identifier
- agent attempt number
- tool name
- tool success/failure
- candidate count
- stop reason
- total agent duration

Do not log hidden chain-of-thought.

If explanations are needed for debugging, log structured action summaries, not private reasoning.

Example:

`agent selected search strategy: ingredients=chicken,rice cuisine=Chinese`

rather than unrestricted internal reasoning text.

---

## 11. Tool Call Logging

Each tool call should record:

- request_id
- tool name
- validated argument summary
- execution duration
- success/failure
- typed error code

Avoid recording full large payloads unless explicitly needed.

---

## 12. Deterministic Engine Logging

For deterministic modules, useful operational fields may include:

### Normalizer

- raw ingredient count
- matched canonical count
- unknown count

### Pantry Matcher

- candidate recipe ID
- pantry coverage percentage
- missing ingredient count

### Cost Engine

- priced missing count
- unknown price count
- estimated purchase cost
- completeness flag

### Constraint Evaluator

- accepted/rejected
- rejection reason

### Ranker

- candidate count
- final ranking score

Do not duplicate the same large data structure in every component log.

---

## 13. Grounding Evidence

For every final recommendation, the system should be able to identify:

- recipe provider
- provider recipe ID
- provider/source URL where available
- local recipe provenance where applicable

A result without valid grounding evidence must not be presented as a normal successful recommendation.

---

## 14. Performance Timing

Measure at minimum:

- total recommendation latency
- RecipeAPI.io latency
- LLM latency
- deterministic evaluation latency
- database lookup latency where materially useful

Performance measurements should support the project targets:

- normal path approximately under 8 seconds
- bounded worst-case target approximately under 15 seconds

These are targets, not reasons to hide failed measurements.

---

## 15. Agent Bound Metrics

Record or derive:

- search attempts used
- provider pages requested
- unique candidates evaluated
- early-stop occurrence
- attempt-limit exhaustion

This helps prove that the agent is bounded.

Expected design defaults include:

- maximum approximately 3 search strategies
- maximum approximately 20 unique candidates

Any configured change must follow governance rules.

---

## 16. Cache Observability

If cache is used, record:

- HIT
- MISS
- STALE
- ERROR

Cache must not obscure source provenance.

A cache hit should still identify the original recipe source/provider.

---

## 17. Failure Taxonomy

Operational logs should use typed failure categories consistent with API standards.

Examples:

- INVALID_REQUEST
- RECIPE_PROVIDER_TIMEOUT
- RECIPE_PROVIDER_RATE_LIMITED
- RECIPE_PROVIDER_UNAVAILABLE
- RECIPE_PROVIDER_MALFORMED_RESPONSE
- PRICE_NOT_FOUND
- COST_INCOMPLETE
- NO_FEASIBLE_RECIPE
- AGENT_ATTEMPT_LIMIT_REACHED
- MALFORMED_TOOL_CALL
- DATABASE_UNAVAILABLE
- INTERNAL_ERROR

Avoid relying solely on free-form exception text.

---

## 18. Health Endpoint

Backend should expose a lightweight health endpoint.

Suggested path:

`GET /api/health`

Minimum response should confirm application process health.

Example:

```json
{
  "status": "ok"
}
Do not make the basic health endpoint dependent on every external provider unless intentionally designing a deeper readiness endpoint.

19. Readiness Checks

If useful for deployment, a separate readiness check may validate:

SQLite accessibility
required database schema
required reference data
configuration presence

External provider live checks should be used carefully because they consume quota and may create false deployment failures.

A manual release smoke test is sufficient for competition MVP if documented.

20. Startup Validation

At application startup, fail clearly for critical missing configuration such as:

required database path invalid
required database schema missing
critical provider configuration missing

Do not wait until the first user request to discover a basic deployment configuration error where validation is straightforward.

21. Provider Credential Check

Do not print credentials during startup validation.

Validate presence/configuration only.

A live provider call should be performed as a controlled smoke test, not uncontrolled startup traffic.

22. Database Operational Checks

Operational verification should be able to confirm:

database exists
database opens
required tables exist
expected reference data exists
no obvious migration mismatch

Do not perform destructive repair automatically.

23. Error Response vs Internal Log

Public error response:

safe
concise
typed
no stack trace
no secrets

Internal log:

enough context for diagnosis
request correlated
sanitized

These are deliberately different outputs.

24. Frontend Error Handling

Frontend should distinguish:

invalid input
no feasible recommendation
temporary provider problem
partial price coverage
generic system failure

Do not present all failures as:

Something went wrong

where a safe, useful explanation is available.

25. Operational Smoke Test

Before release, manually verify at minimum:

frontend loads
health endpoint works
backend receives request
RecipeAPI.io call works
LLM tool path works
deterministic evaluation works
recommendation renders
local curated provider works
price lookup works
a controlled failure path is understandable
logs contain request IDs
logs do not expose secrets
26. Incident Handling

For competition MVP, formal incident-management tooling is not required.

If a material failure occurs:

capture request ID
reproduce if safe
identify failure category
inspect relevant logs
determine affected component
create remediation finding if material
implement through authorized ticket
verify correction
update project status if readiness changed
27. Production Debugging Rule

Do not make uncontrolled emergency changes directly in production.

If urgent:

identify issue
create bounded fix
test
review
deploy
verify
preserve Git history

If temporary diagnostic logging is enabled, remove or reduce it after investigation.

28. Evidence Retention

Competition evidence should be lightweight.

Useful retained evidence may include:

CI output
release smoke-test notes
benchmark/timing output
screenshots
deployment logs
provider failure test output
PR review records

Do not retain unnecessary secret-bearing logs.

29. Observability Acceptance Criteria

Before competition release:

recommendation requests have request IDs
external calls have duration/status logging
provider failures map to typed errors
agent bounds are observable
final recommendations preserve source identity
critical errors are diagnosable
no credentials appear in logs
health endpoint works
smoke-test procedure has been executed
30. Competition-Speed Rule

Do not introduce heavyweight observability infrastructure unless deployment requires it.

For the MVP, prefer:

Python structured logging
deployment platform logs
request IDs
typed errors
simple timings
manual smoke checks

The goal is diagnosability and evidence, not infrastructure complexity.
