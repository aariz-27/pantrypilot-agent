# PantryPilot System Context

## 1. Purpose

This document defines PantryPilot's actors, internal components, external services, trust boundaries, data flows, ingress/egress points, and sensitive-data locations.

It supports later threat modeling and security review.

---

## 2. Primary Actors

### End User

A person using PantryPilot to find suitable recipes from ingredients they already have.

The user may provide:

- pantry ingredients
- optional budget
- cuisine preference
- servings
- excluded ingredients
- optional total meal-time limit if enabled

The user is untrusted input.

---

## 3. Internal Application Components

### React Frontend

Responsibilities:

- collect user inputs
- send requests to backend
- render user-safe agent progress
- display recommendations
- display recipe details
- display limitations and errors

Trust level:

Untrusted client environment.

The frontend is never an authoritative business-logic layer.

### FastAPI Backend

Responsibilities:

- request validation
- request IDs
- API contracts
- orchestration entry point
- error mapping
- backend security boundaries

Trust level:

Trusted application boundary.

### PantryPilot Agent Orchestrator

Responsibilities:

- maintain recommendation goal/state
- select tools
- choose search strategy
- decide retry/replan/stop behavior

Trust level:

Controlled decision component.

The LLM itself is not trusted for factual arithmetic or source truth.

### Deterministic Tools

Includes:

- ingredient normalization
- pantry matching
- price lookup
- cost calculation
- constraint evaluation
- deterministic ranking

Trust level:

Authoritative for calculations within their defined contract.

### Recipe Service

Responsibilities:

- provider-neutral recipe search
- recipe detail retrieval
- provider routing
- provider DTO normalization

### SQLite

Stores approved local/runtime data such as:

- ingredient aliases
- reference prices
- curated recipes
- curated recipe ingredients
- permitted cache data
- lightweight usage/runtime metadata

---

## 4. External Services

### RecipeAPI.io

Purpose:

Primary live recipe provider.

Data exchanged:

Outbound:
- search parameters
- recipe identifiers

Inbound:
- recipe names
- ingredients
- measures
- instructions
- cuisine/category metadata
- images/source metadata
- prep/cook information where available

Trust level:

External untrusted provider data.

Provider data must be schema validated.

### LLM Provider

Purpose:

Powers the PantryPilot decision agent.

Data exchanged:

Outbound:
- user goal/state
- compact tool observations
- available tool definitions
- approved system instructions

Inbound:
- tool calls
- bounded decision outputs
- user-safe summary text where applicable

Trust level:

External probabilistic decision service.

The LLM is not authoritative for recipe facts, prices, calculations, or hard constraints.

### Deployment Platform

Purpose:

Hosts frontend/backend.

Exact provider is currently an open decision.

Trust/security requirements will depend on the selected host.

---

## 5. Offline/Development Services

### Apify

Purpose:

One-time development-time acquisition of UAE grocery reference pricing.

Apify is not part of the normal runtime recommendation path.

Data flow:

Apify
→ raw grocery data
→ offline cleaning/normalization
→ SQLite reference data

Runtime PantryPilot must not depend on live Apify access.

### Claude Code

Purpose:

Implementation agent.

Claude Code is not a runtime application component.

It operates on the repository only under authorized ticket/governance rules.

### GitHub

Purpose:

- authoritative code repository
- project governance memory
- pull requests
- history
- review evidence
- implementation traceability

GitHub is part of the development/governance system, not the end-user runtime path.

---

## 6. Core Runtime Data Flow

```text
User
  |
  | pantry / budget / cuisine / exclusions / servings
  v
React Frontend
  |
  | HTTPS API request
  v
FastAPI Backend
  |
  v
Agent Orchestrator
  |
  | chooses action
  +------------------------------+
  |                              |
  v                              v
Recipe Service              Deterministic Tools
  |                              |
  v                              v
RecipeAPI.io                  SQLite
or Local Curated Source      aliases / prices / cache
  |
  v
Normalized Recipe DTO
  |
  v
Matcher / Cost / Constraints / Ranker
  |
  v
Structured Observation
  |
  v
Agent decides retry / paginate / reformulate / stop
  |
  v
FastAPI Response
  |
  v
React UI
  |
  v
User

7. Trust Boundaries
TB-01 User → Frontend

User input is untrusted.

Risks include:

oversized input
malformed text
prompt-injection-like text
unexpected Unicode
malicious strings

Controls:

frontend limits
backend Pydantic validation
normalization
safe rendering
TB-02 Frontend → Backend

Frontend cannot be trusted to enforce authoritative rules.

Controls:

backend revalidates all inputs
backend owns business limits
no secrets in frontend
TB-03 Backend → LLM

The backend sends structured state and tool definitions to an external AI service.

Risks:

prompt/tool abuse
model hallucination
malformed tool arguments
excessive loops

Controls:

system policy
allow-listed tools
schema validation
bounded attempts
deterministic hard constraints
TB-04 Backend → RecipeAPI.io

External recipe provider is untrusted.

Risks:

malformed payloads
timeout
429
unexpected fields
prompt-like content embedded in recipe text
unsafe URLs

Controls:

timeout
schema validation
typed errors
provider adapter
bounded pagination
normal frontend escaping
TB-05 Backend → SQLite

SQLite is trusted local storage, but application access must still be controlled.

Controls:

repository abstraction
parameterized access
constraints
validated seed/import data
TB-06 Offline Grocery Data → Runtime DB

Raw scraped/acquired grocery data is untrusted until normalized.

Controls:

offline validation
canonicalization
deduplication
price validation
manual sampling
source/date retention
8. Ingress Points

Primary runtime ingress:

POST /api/recommend
GET /api/ingredients/suggest
GET /api/recipes/{provider}/{id}
GET /api/health

Future endpoints must be added to this document before external exposure.

9. Egress Points

External runtime egress:

RecipeAPI.io API
LLM provider API

Development/offline egress:

Apify acquisition
deployment provider
GitHub

No user-supplied arbitrary outbound URL fetching is allowed.

10. Sensitive Data

PantryPilot MVP intentionally minimizes sensitive data.

Secrets

Sensitive:

LLM API key
RecipeAPI.io API key
deployment secrets

Location:

Backend environment variables / deployment secret store.

Never:

commit to Git
expose to frontend
log
User Inputs

Typical pantry/preferences are low sensitivity but should still not be unnecessarily retained.

Policy:

session/request scoped where possible
avoid long-term storage
avoid logging full raw input unless needed for debugging and explicitly redacted
Provider Data

Not generally sensitive, but treated as untrusted external data.

Price Dataset

Not sensitive.

Must retain provenance and collection date.

11. Authentication and Authorization

MVP currently has:

no user accounts
no authentication
no tenant model
no admin interface

Therefore:

tenant isolation is NOT APPLICABLE to the current MVP
authorization boundaries are minimal
public API abuse/rate limiting remains applicable

If authentication, user accounts, or multi-user persisted state are later introduced, this system context and threat model must be revised before implementation.

12. Queues and Background Workers

Current MVP:

NOT APPLICABLE.

No message queue or background worker is required for the approved architecture.

If asynchronous background processing is later introduced, queue ownership, retry behavior, duplicate handling, and dead-letter behavior must be designed before implementation.

13. Object Storage

Current MVP:

NOT APPLICABLE.

PantryPilot does not upload or persist user files/images.

Recipe images are referenced from approved provider metadata where permitted.

14. Payments and Financial Transactions

Current MVP:

NOT APPLICABLE.

Budget is a recommendation constraint only.

PantryPilot does not:

charge users
purchase groceries
process payments
create financial transactions
15. Real-World Action Boundary

PantryPilot is advisory/decision-support only.

It does not:

place grocery orders
contact restaurants
make payments
modify external inventory
perform irreversible real-world actions

This materially reduces runtime action risk.

16. Primary Security Concerns

Most relevant MVP concerns are:

prompt/tool misuse
external recipe-data injection
secrets exposure
API abuse
malformed provider responses
unsafe rendering
unbounded agent loops
excessive external calls
dependency/supply-chain issues
logging sensitive configuration
17. Primary Reliability Concerns
RecipeAPI.io timeout
RecipeAPI.io 429
malformed provider data
LLM timeout
malformed LLM tool call
SQLite unavailable
missing price
unsupported unit
no feasible recipe
bounded retry exhaustion
18. Primary Performance Concerns
unnecessary provider calls
unnecessary LLM calls
deep pagination
evaluating too many candidates
repeated DB lookups
large recipe payloads
blocking external I/O
19. Context Change Rule

This document must be updated before implementing any material addition involving:

authentication
accounts
file upload
image recognition
payment
ordering
additional provider
background worker
queue
object storage
multi-tenant behavior
persistent user history
admin interface
new externally reachable endpoint
