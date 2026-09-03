# PantryPilot AI Delivery Operating Model

## Purpose

This document defines the permanent delivery workflow for PantryPilot.

The repository is the authoritative project memory.
ChatGPT and Claude Code must operate from repository state, not informal chat history.

---

## Roles

### Founder / Product Owner

Responsibilities:

- approve product decisions
- approve architecture decisions where required
- authorize implementation tickets
- approve accepted risks
- perform final merge
- approve scope changes

The Founder is the final merge authority.

### ChatGPT

Acts as:

- Solution Architect
- Technical Governance Reviewer
- Security Reviewer
- Performance/Reliability Reviewer
- Independent GitHub PR Reviewer

Responsibilities:

- verify ticket authorization
- verify decision and ADR compliance
- review architecture
- review functional correctness
- review data integrity
- review security
- review performance
- review reliability
- review concurrency/idempotency where applicable
- inspect actual PR diff/code/tests
- verify remediation
- recommend merge or block

ChatGPT does not replace Founder merge authority.

### Claude Code

Acts as:

- implementation agent
- test-writing agent
- first-pass code quality reviewer
- first-pass security/performance/reliability reviewer

Claude must:

- work only on authorized ticket scope
- write tests
- run tests
- self-review
- report evidence
- stop on material ambiguity
- never merge

---

# Permanent Delivery Lifecycle

PRE-FLIGHT  
→ AUTHORIZATION  
→ IMPLEMENTATION  
→ CLAUDE SELF-REVIEW  
→ PR  
→ CHATGPT INDEPENDENT REVIEW  
→ CORRECTION PASS  
→ CHATGPT FINAL RE-REVIEW  
→ FOUNDER MERGE  
→ POST-MERGE CLOSURE

---

## 1. Pre-Flight

Before implementation begins:

- confirm authorized ticket
- confirm branch
- confirm relevant requirements
- review DECISION_REGISTER.md
- review relevant ADRs
- review decision triggers
- review remediation findings
- review dependencies
- review security requirements
- review technical architecture
- identify unresolved assumptions

If a material unresolved decision affects the ticket:

STOP.

No implementation from silence.

---

## 2. Authorization

A ticket is authorized only when:

- Founder has approved work to begin
- scope is explicit
- branch is identified
- requirements are linked
- dependencies are satisfied
- decision blockers are satisfied or explicitly deferred by authority

Claude may not begin unrelated work.

---

## 3. Implementation

Claude implements only the authorized ticket.

Rules:

- no unrelated cleanup
- no feature expansion
- no architecture redesign
- no hidden dependency changes
- no new provider assumptions
- no changes outside permitted files unless approved

---

## 4. Claude Self-Review

Before opening or finalizing a PR, Claude must review:

### Functional Correctness

- acceptance criteria
- edge cases
- input validation
- error behavior
- state transitions

### Data Integrity

- authoritative state
- duplicate prevention
- transaction boundaries
- rollback behavior
- persistence correctness

### Security

- input handling
- secret handling
- prompt/tool abuse
- injection risks
- unsafe external data
- API exposure

### Performance

- unnecessary external API calls
- unbounded loops
- unbounded candidate processing
- repeated DB queries
- large payloads
- blocking I/O

### Reliability

- retries
- timeouts
- partial failures
- bounded agent behavior
- provider failure handling

### Concurrency / Idempotency

Where applicable:

- duplicate requests
- repeated tool execution
- race conditions
- duplicate persisted actions

### Testing

- unit tests
- integration tests
- negative tests
- regression tests
- provider-contract tests where relevant

### Escape-Path Review

Claude must explicitly answer:

> Is there another public/internal API, background path, direct database path, alternate tool call, or alternate call sequence that can produce the same outcome while bypassing the control implemented in this ticket?

---

## 5. Pull Request

Every PR must:

- reference ticket ID
- reference requirement IDs
- reference decision dependencies
- state exact scope
- state what changed
- state what did not change
- list tests run
- include security/performance/reliability impact
- include escape-path review
- identify known limitations
- identify residual risks

Claude must not merge.

---

## 6. ChatGPT Independent Review

ChatGPT reviews in this exact order:

1. Authorization
2. Decision / ADR Compliance
3. Requirements
4. Scope
5. Architecture
6. Functional Correctness
7. Data Integrity
8. Security
9. Performance
10. Reliability
11. Concurrency
12. Tests
13. Escape Paths
14. Operability
15. Governance Closure

ChatGPT must inspect actual code, diff, and tests.

Claude's summary is evidence pointer only, not proof.

---

## 7. Correction Pass

If issues are found:

- findings must be recorded
- Claude receives a bounded correction task
- no unrelated changes
- regression tests must be added for confirmed defects where applicable

---

## 8. ChatGPT Final Re-Review

After corrections:

- verify finding resolution
- verify tests
- verify no new regression
- verify no architecture drift
- verify governance records are updated

Result:

- MERGE RECOMMENDED
or
- MERGE BLOCKED

---

## 9. Founder Merge

Founder performs final merge.

No automated or AI agent merge unless explicitly delegated.

---

## 10. Post-Merge Closure

After merge:

- verify GitHub merge state
- update ticket status
- update requirements traceability
- update CURRENT_STATUS.md if material
- update PROJECT_HISTORY.md
- update decision subsequent status if relevant
- update remediation register if findings changed
- record test/evidence references

Merge does not equal administrative closure.

---

# PantryPilot-Specific Rules

## Agentic Architecture

The LLM must control meaningful decisions:

- recipe search strategy
- ingredient combination selection
- whether to paginate
- whether to reformulate search
- whether to inspect more candidates
- when to stop

Python owns:

- normalization
- pantry matching
- cost calculation
- hard constraints
- ranking
- numeric logic

A fixed deterministic workflow followed by LLM explanation is not acceptable.

## Grounding

PantryPilot must never invent:

- recipes
- recipe ingredients
- recipe instructions
- prices
- provider results
- deterministic ranking values

## Provider Boundaries

RecipeAPI.io remains behind the provider abstraction.

Local curated recipes must use the same internal Recipe DTO.

Vendor-specific fields must not leak into domain logic.

## Competition Scope

Do not introduce:

- multi-agent orchestration
- real grocery ordering
- restaurant ordering
- live grocery scraping
- nutrition/medical claims
- image recognition
- user accounts
- unnecessary ERP-style features

unless Founder explicitly changes scope.

---

# Repeated Defect Rule

If the same defect class occurs twice, create a structural control where feasible:

- CI check
- invariant test
- architecture rule
- validation
- DB constraint
- automated governance check

Do not continue relying only on manual correction.

---

# Capability Maturity

Use these states when applicable:

- DESIGNED
- FOUNDATION_IMPLEMENTED
- BUSINESS_PATH_IMPLEMENTED
- PROVIDER_GATED
- PILOT_BLOCKED
- PILOT_READY
- PRODUCTION_READY

A completed ticket does not automatically advance capability maturity.
