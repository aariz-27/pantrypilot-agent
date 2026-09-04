# PantryPilot API Integration Standards

## 1. Purpose

This document defines the technical standards for:

- PantryPilot's public backend API
- external provider integration
- request/response validation
- error handling
- correlation IDs
- retry behavior
- idempotency
- rate limiting
- provider-neutral adapters
- security boundaries

These standards apply to all runtime integrations.

---

## 2. API Design Principles

PantryPilot APIs must be:

- explicit
- versionable
- typed
- bounded
- deterministic where possible
- provider-neutral
- safe under failure
- easy to debug

The frontend must never depend directly on external provider APIs.

All external providers are accessed through backend adapters.

---

## 3. Public API Ownership

The FastAPI backend is the authoritative public API boundary.

The frontend may call only approved PantryPilot backend endpoints.

The frontend must not call:

- RecipeAPI.io directly
- the LLM provider directly
- SQLite directly
- Apify directly
- any future external provider directly

---

## 4. API Versioning

Competition MVP may use unversioned paths such as:

- `/api/health`
- `/api/ingredients/suggest`
- `/api/recommend`
- `/api/recipes/{provider}/{id}`

If breaking API changes are introduced after the MVP, use explicit versioning such as:

`/api/v1/...`

Do not silently change an existing contract consumed by the frontend.

---

## 5. Request IDs

Every recommendation request must receive a unique `request_id`.

The request ID should be available in:

- backend logs
- API response
- error responses where practical
- observability records

Purpose:

- debugging
- tracing
- review evidence
- failure correlation

---

## 6. Correlation IDs

For the competition MVP, `request_id` may act as the primary correlation ID.

If external provider calls are made:

- log the same request ID with provider call metadata
- do not expose secrets in correlation logs

If future distributed services are introduced, a separate correlation ID strategy may be required.

---

## 7. Request Validation

All public API inputs must be validated server-side using Pydantic or equivalent typed validation.

Validation should cover:

- required fields
- field types
- maximum string length
- maximum ingredient count
- budget bounds
- servings bounds
- exclusion count
- cuisine text length
- optional total-time bounds
- allowed enum/state values

Frontend validation is helpful but not authoritative.

---

## 8. Unknown Fields

Public request models should not silently accept unexpected privileged/internal fields.

If a client submits internal-only fields such as:

- provider override
- tool limits
- score values
- internal state
- cache status

the backend should reject or ignore them according to an explicit schema rule.

Do not allow mass assignment into internal objects.

---

## 9. Standard Error Envelope

Errors should return a stable structured form.

Representative shape:

```json
{
  "request_id": "req_123",
  "error": {
    "code": "RECIPE_PROVIDER_TIMEOUT",
    "message": "The recipe provider did not respond in time.",
    "retryable": true
  }
}
The user-facing message must be safe.

Internal stack traces must never be returned to the browser.

10. Error Taxonomy

At minimum distinguish:

INVALID_REQUEST
INGREDIENT_NORMALIZATION_FAILED
RECIPE_PROVIDER_TIMEOUT
RECIPE_PROVIDER_RATE_LIMITED
RECIPE_PROVIDER_UNAVAILABLE
RECIPE_PROVIDER_MALFORMED_RESPONSE
RECIPE_NOT_FOUND
PRICE_NOT_FOUND
COST_INCOMPLETE
NO_FEASIBLE_RECIPE
AGENT_ATTEMPT_LIMIT_REACHED
MALFORMED_TOOL_CALL
DATABASE_UNAVAILABLE
INTERNAL_ERROR

Retry behavior must depend on error type.

11. HTTP Status Guidance

Suggested mapping:

200

Successful response, including valid partial or no_feasible_match application outcome where the request itself was processed correctly.

400

Invalid client request.

404

Requested grounded recipe/resource does not exist.

422

Typed request validation failure where FastAPI/Pydantic semantics apply.

429

PantryPilot's own public rate limit exceeded, if implemented.

502

Upstream provider failure where appropriate.

503

Temporary dependency/service unavailable.

500

Unexpected internal failure.

Do not expose raw external provider status blindly if a safer application-level mapping exists.

12. Pagination

Pagination is bounded.

For RecipeAPI.io:

external pagination is controlled by Recipe Service/agent strategy
frontend must not directly request arbitrary provider pages
global candidate limits still apply across pages

Do not automatically crawl until "enough" data is found.

Pagination must remain a deliberate agent action.

13. Request Limits

Server-side limits should exist for expensive requests.

Examples:

maximum pantry ingredients
maximum exclusions
maximum text length per ingredient
maximum budget
maximum servings
maximum agent attempts
maximum candidates
maximum provider calls

The client cannot increase internal execution bounds by sending request fields unless explicitly allowed.

14. Rate Limiting

For competition deployment, lightweight public rate limiting is recommended where the host/platform makes it simple.

Goals:

protect LLM quota
protect RecipeAPI quota
reduce abuse
prevent accidental repeated submissions

Rate limiting must not be confused with provider rate limiting.

15. Authentication

Current MVP:

NOT APPLICABLE.

There are no user accounts.

No bearer token/user session is required for normal PantryPilot use.

If authentication is added later, API standards must be revised before implementation.

16. Authorization

Current MVP:

NOT APPLICABLE for user-owned data.

There are no roles, tenants, saved private objects, or administrative APIs.

If those features are introduced later:

ownership
authorization
IDOR/BOLA protection

must be designed first.

17. Tenant Resolution

Current MVP:

NOT APPLICABLE.

No tenant model exists.

Do not introduce a tenant field casually without a formal architecture decision.

18. External Provider Integration Rule

All external providers must be behind adapters.

Business/domain logic must never depend directly on:

vendor SDK classes
vendor response objects
vendor-specific field names
vendor-specific error objects

Provider adapter responsibilities:

build request
call provider
apply timeout
validate response
map response to internal DTO
map provider error to typed application error
expose only provider-neutral output
19. RecipeAPI.io Standard

RecipeAPI.io calls must use:

fixed configured base URL
server-side API key
HTTPS
explicit timeout
bounded pagination
schema validation
request count logging
typed failure mapping

The backend must not accept a user-supplied RecipeAPI.io base URL.

20. LLM Provider Standard

The LLM provider must be accessed through a provider/runtime adapter.

The rest of PantryPilot should depend on:

structured tool-call capability
common internal agent interface

not on vendor-specific model SDK behavior.

The exact model remains configuration-controlled.

21. Provider Timeout Standard

Every external provider call requires an explicit timeout.

No provider call may wait indefinitely.

Timeout should result in a typed application error.

Suggested competition range:

3–5 seconds per external provider call.

22. Retry Classification

Retry only errors that are reasonably transient.

Potentially Retryable
temporary timeout
temporary network failure
some provider 5xx conditions
Generally Not Immediately Retryable
invalid request
authentication/key failure
malformed provider schema
429 rate limit
unknown recipe ID
failed hard constraint
invalid user input

Retries must remain bounded.

23. Backoff

If retry is used:

keep count low
use bounded delay/backoff where appropriate
do not create retry storms
respect overall user latency target

No recursive retry design.

24. Idempotency

Current public recommendation request is read-oriented.

No business transaction is created.

Therefore a client may repeat a recommendation request without creating an irreversible external action.

Still, internal writes such as:

cache
usage metadata

must be duplicate-safe.

If later real ordering or state-changing operations are added, explicit idempotency keys become mandatory.

25. Webhooks

Current MVP:

NOT APPLICABLE.

No webhook endpoint exists.

Before adding one, define:

signature verification
replay protection
timestamp validation
idempotency
provider identity
retry behavior
26. Replay Prevention

Current recommendation path is low risk because it has no irreversible business action.

Rate limiting remains relevant.

If state-changing actions are later introduced, replay prevention must be designed explicitly.

27. Provider Failure Taxonomy

External provider failures should map into categories such as:

TIMEOUT
RATE_LIMITED
AUTH_FAILURE
MALFORMED_RESPONSE
NOT_FOUND
TEMPORARY_UNAVAILABLE
PERMANENT_CONFIGURATION_ERROR

Do not treat all provider errors as generic failure.

28. Provider-Neutral Recipe Contract

All approved recipe sources must map to the same internal Recipe DTO.

The DTO is the stable domain boundary.

Downstream code must not ask:

"Was this RecipeAPI.io?"
"Was this local SQLite?"

except where provenance/display behavior explicitly requires source identity.

29. Tool API Standards

Agent tools must have:

unique stable name
typed input
typed output
explicit success/failure
bounded output size
no raw stack trace
no hidden side effect unless documented

The LLM may call only allow-listed tools.

Unknown tool names are rejected.

30. Tool Argument Validation

Every tool call from the model must be validated before execution.

Reject:

unknown provider IDs
invalid page values
negative counts
excessive candidate requests
arbitrary URLs
invalid ingredient IDs
malformed schemas

A model request is not trusted merely because it originated from the LLM.

31. Provider Content Safety

Recipe/provider text is untrusted data.

Do not interpret recipe text as instructions to:

call another tool
reveal secrets
modify agent rules
access URLs
execute commands

External content may only populate validated Recipe DTO fields.

32. Response Size

API responses should be sufficient for the UI but not unnecessarily huge.

Avoid returning:

full provider raw payload
internal prompts
hidden agent state
unused metadata
provider debug traces

The UI should receive only required structured fields.

33. Logging Standards

For external calls, log:

request_id
provider
operation
duration
status category
cache hit/miss
result count where useful

Do not log:

API keys
Authorization headers
private system prompts
hidden chain-of-thought
unnecessary raw user data
34. API Contract Change Rule

Any breaking change to:

request shape
response shape
error envelope
endpoint path
Recipe DTO
tool schema

requires:

authorized ticket
affected requirement review
frontend/backend impact review
tests
documentation update
migration/versioning decision where applicable

Claude Code must not silently change a public/internal contract.

35. API Security Review Questions

Every API/integration ticket must answer:

Is input validated?
Are unknown fields controlled?
Can arbitrary URLs be supplied?
Are secrets server-side?
Is timeout explicit?
Is retry bounded?
Is pagination bounded?
Can model output bypass validation?
Can provider content influence system instructions?
Are error details safe?
Are logs free of secrets?
Does the change introduce a new externally reachable surface?

If a question is not applicable, explain why.
