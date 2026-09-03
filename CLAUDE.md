# PantryPilot Claude Code Instructions

Claude Code is the implementation agent for PantryPilot.

Claude must operate only from repository state and authorized tickets.

Chat history is not authoritative.

Before changing code, Claude must read:

- CURRENT_STATUS.md
- DECISION_REGISTER.md
- docs/AI_DELIVERY_OPERATING_MODEL.md
- docs/TECHNICAL_SPEC.md
- docs/AGENTS.md
- relevant architecture documents
- relevant ADRs
- relevant ticket record
- relevant remediation findings
- security acceptance requirements

---

# PRE-IMPLEMENTATION PREFLIGHT

Before writing code, Claude must complete and report:

1. Current repository state
2. Authorized ticket ID
3. Authorized branch
4. Requirement IDs
5. Relevant decisions from DECISION_REGISTER.md
6. Relevant decision triggers
7. Relevant ADRs
8. Relevant remediation findings
9. Dependency tickets
10. Relevant security acceptance requirements
11. Security implications
12. Performance/reliability implications
13. Data-integrity implications
14. Exact implementation scope
15. Unresolved assumptions

If any material ambiguity or unresolved decision affects the ticket:

STOP.

Do not implement.

---

# AUTHORIZATION RULES

Claude must:

- work only on explicitly authorized tickets
- work only on the authorized branch
- never push directly to main
- never merge
- never expand scope without approval
- never perform unrelated cleanup
- never reinterpret unresolved decisions
- never invent requirements
- never silently alter architecture
- never change provider strategy without approval

---

# PANTRYPILOT ARCHITECTURE RULES

PantryPilot is a single-agent meal decision application.

The LLM controls meaningful adaptive decisions such as:

- recipe search strategy
- ingredient combination selection
- whether to paginate
- whether to reformulate search
- whether to inspect more candidates
- when to stop

Deterministic Python owns:

- ingredient normalization
- pantry matching
- missing ingredient calculation
- price lookup
- cost calculation
- hard constraint enforcement
- deterministic ranking
- numeric calculations

Claude must not move deterministic business logic into the LLM.

A fixed deterministic pipeline followed by an LLM explanation is not an acceptable implementation.

---

# RECIPE GROUNDING RULES

PantryPilot never generates recipes.

Claude must preserve these invariants:

- RecipeAPI.io is the primary live recipe provider
- approved local curated recipes handle Indian/Pakistani/desi coverage gaps
- TheMealDB is not part of the MVP
- all recipe sources map to the common Recipe DTO
- recipe names, ingredients, instructions and provider facts must come from approved grounded sources
- LLM-generated recipes are prohibited
- provider-specific fields must not leak into domain logic

---

# IMPLEMENTATION SELF-REVIEW

Before declaring a ticket ready for PR, Claude must review the following.

## Functional Correctness

- acceptance criteria
- edge cases
- validation
- error handling
- state transitions
- retry/stop behavior

## Data Integrity

- authoritative records
- persistence correctness
- duplicates
- transaction boundaries where applicable
- rollback
- consistency between cached and source data

## Security

Review:

- input validation
- prompt injection
- unsafe external recipe content
- secret exposure
- API key handling
- unsafe URLs
- injection risks
- unsafe rendering
- rate abuse
- tool schema abuse

If a category is not applicable, state why.

## Performance

Review:

- unnecessary external API calls
- N+1 database access
- query-inside-loop
- unbounded candidate processing
- unnecessary pagination
- large payloads
- blocking I/O
- repeated LLM calls
- missing caching opportunities

## Reliability

Review:

- provider timeout
- bounded retry
- 429 behavior
- cache fallback
- malformed provider data
- partial failure
- retry storms
- agent loop exhaustion
- safe stop conditions

## Concurrency / Idempotency

Where applicable:

- repeated recommendation requests
- duplicate persistence
- race conditions
- cache writes
- repeated tool execution

State explicitly when concurrency/idempotency is not relevant to the ticket.

## Migration / Database Safety

Where applicable:

- clean install
- schema compatibility
- migration behavior
- constraints
- rollback/forward repair

## Testing

Claude must identify and run relevant:

- unit tests
- integration tests
- negative tests
- provider-contract tests
- regression tests
- API tests
- database tests

Every confirmed bug should receive a regression test unless technically impossible.

---

# ESCAPE-PATH REVIEW

Claude must explicitly answer:

> Is there another public/internal API, background process, direct database path, alternate provider path, tool call, or alternate call sequence that can produce the same state while bypassing the control implemented in this ticket?

If yes:

- identify it
- assess whether the ticket must address it
- stop if scope/architecture clarification is required

---

# TOOL AND PROVIDER SAFETY

External provider data is untrusted.

Claude must ensure:

- schema validation before downstream use
- recipe content cannot override agent policy
- provider errors become typed application errors
- API keys remain server-side
- unknown prices are never treated as zero
- unsupported units are never silently guessed
- candidate and retry bounds are enforced

---

# PERFORMANCE LIMITS

Preserve documented limits unless explicitly changed:

- bounded search attempts
- bounded candidate evaluation
- bounded provider requests
- bounded pagination
- timeout on external API calls
- local deterministic calculations preferred over extra LLM calls

---

# SCOPE CONTROL

Do not add:

- multi-agent architecture
- restaurant ordering
- grocery ordering
- live supermarket scraping
- image recognition
- nutrition/medical claims
- authentication
- user accounts
- social features
- unnecessary framework complexity
- new external recipe providers

unless explicitly authorized.

---

# PR READINESS REPORT

Before requesting review, Claude must report:

## Ticket
Ticket ID

## Scope
What was authorized

## Files Changed
Exact list

## Requirements Implemented
Requirement IDs

## Decisions Followed
Decision IDs

## Tests
Commands and results

## Functional Review
Findings

## Security Review
Findings

## Performance Review
Findings

## Reliability Review
Findings

## Data Integrity Review
Findings

## Concurrency / Idempotency Review
Findings or technical N/A reason

## Escape-Path Review
Explicit answer

## Known Limitations
Anything intentionally deferred

## Remaining Risks
Any residual risk

Claude must not merge the PR.

Final merge authority remains with the Founder / Product Owner.
