# PantryPilot Threat Model

## 1. Purpose

This document identifies the main security threats relevant to the PantryPilot competition MVP.

PantryPilot has no authentication, no payments, no multi-tenant persisted user data, no file uploads, and no real-world purchase action.

Therefore the threat model focuses on:

- public API exposure
- LLM/tool abuse
- prompt injection
- external provider trust
- secrets
- unsafe rendering
- data integrity
- resource exhaustion
- dependency risk
- CI/CD and repository integrity

Threats are not marked NOT APPLICABLE without a technical reason.

---

## 2. Assets

Important assets include:

- source code
- GitHub repository
- API keys
- LLM provider credentials
- RecipeAPI.io credentials
- deployment credentials
- system prompts/tool definitions
- SQLite reference database
- curated recipe dataset
- ingredient aliases
- reference pricing data
- user request inputs
- recommendation outputs
- logs
- CI/CD configuration
- release artifacts

---

## 3. Actors

### End User

Uses the public PantryPilot interface.

Trust level:
Untrusted.

### Founder / Product Owner

Approves scope, decisions, and merges.

Trust level:
Privileged development actor.

### Claude Code

Implementation agent.

Trust level:
Controlled development tool, not final authority.

### ChatGPT

Architecture/review role.

Trust level:
Advisory/governance actor, not merge authority.

### External LLM Provider

External decision service.

Trust level:
Untrusted external dependency for factual truth.

### RecipeAPI.io

External recipe provider.

Trust level:
Untrusted external data source.

### Deployment Platform

External hosting environment.

Trust level:
Privileged infrastructure provider.

---

## 4. Trust Boundaries

TB-01:
User → React frontend

TB-02:
React frontend → FastAPI backend

TB-03:
FastAPI backend → LLM provider

TB-04:
FastAPI backend → RecipeAPI.io

TB-05:
FastAPI backend → SQLite

TB-06:
Offline grocery acquisition → normalized SQLite dataset

TB-07:
Developer workstation/Claude Code → GitHub repository

TB-08:
GitHub/CI → deployment platform

---

## 5. Entry Points

Runtime entry points:

- `POST /api/recommend`
- `GET /api/ingredients/suggest`
- `GET /api/recipes/{provider}/{id}`
- `GET /api/health`

Development entry points:

- GitHub pull requests
- CI workflows
- dependency updates
- data import scripts
- environment configuration

---

## 6. Sensitive Data

Sensitive:

- LLM API key
- RecipeAPI.io API key
- deployment credentials
- repository secrets

Low-sensitivity user data:

- pantry ingredients
- budget
- cuisine
- exclusions
- servings

No intended PII is stored in the MVP.

---

## 7. Threat Catalogue

### T-01 SQL Injection

**Applicability:** REQUIRED/APPLICABLE

Risk:
Untrusted inputs could reach SQLite queries.

Controls:

- parameterized SQL
- repository layer
- no raw SQL built from user strings
- input validation
- DB tests

Evidence required:

- repository tests
- code review

---

### T-02 NoSQL Injection

**Applicability:** NOT APPLICABLE

Reason:
No NoSQL database is used in the MVP.

Revisit if a NoSQL store is added.

---

### T-03 Command Injection

**Applicability:** REQUIRED/APPLICABLE

Risk:
User/provider input could be passed to shell/process execution.

Controls:

- runtime application must not execute user-supplied shell commands
- no shell-based recipe processing
- import scripts must not interpolate untrusted strings into shell commands

---

### T-04 Server-Side Template Injection

**Applicability:** NOT APPLICABLE / LOW

Reason:
No server-side templating engine is planned.

React renders frontend content.

Revisit if server-side templates are introduced.

---

### T-05 ReDoS

**Applicability:** CONDITIONAL

Risk:
Unsafe complex regex on attacker-controlled ingredient text could consume CPU.

Controls:

- avoid complex catastrophic regex
- bounded input length
- simple normalization patterns

---

### T-06 SSRF

**Applicability:** REQUIRED/APPLICABLE

Risk:
A user or LLM could cause backend to fetch arbitrary URLs.

Controls:

- backend only calls allow-listed provider endpoints
- no arbitrary URL fetch tool
- source URLs are data only
- recipe URLs are never fetched based solely on model/user instruction

---

### T-07 XSS

**Applicability:** REQUIRED/APPLICABLE

Risk:
Recipe provider content may contain malicious HTML/script-like strings.

Controls:

- standard React escaping
- no `dangerouslySetInnerHTML`
- no raw HTML rendering
- validate external URLs where rendered

---

### T-08 CSRF

**Applicability:** LOW / CONDITIONAL

Reason:
No authenticated session or state-changing user action exists in the MVP.

If cookies/auth/state-changing operations are added, reassess.

---

### T-09 IDOR / BOLA

**Applicability:** LOW / CONDITIONAL

Reason:
No user-owned records or authenticated object ownership exists.

Still validate requested recipe/provider IDs.

Revisit if accounts or user-specific saved data are added.

---

### T-10 Path Traversal

**Applicability:** REQUIRED/APPLICABLE for development/import paths

Risk:
Unsafe file path handling in scripts or local data access.

Controls:

- fixed repository-controlled data paths
- no user-controlled filesystem path
- validate any future file parameter

---

### T-11 Unsafe Deserialization

**Applicability:** REQUIRED/APPLICABLE

Risk:
Untrusted provider/cache data deserialized into unsafe object types.

Controls:

- JSON only
- Pydantic/schema validation
- no pickle/untrusted executable serialization

---

### T-12 Mass Assignment

**Applicability:** CONDITIONAL

Risk:
Client payload could populate fields that should be server-controlled.

Controls:

- explicit Pydantic request models
- reject unexpected privileged fields
- no generic ORM object construction from raw request dictionaries

---

### T-13 Parameter Tampering

**Applicability:** REQUIRED/APPLICABLE

Risk:
User modifies budget, limits, provider selection, or hidden fields.

Controls:

- backend validation
- server-owned bounds
- no client authority over internal tool limits
- no arbitrary provider selection unless API contract allows it

---

### T-14 Unsafe Redirects

**Applicability:** LOW

Reason:
No redirect-based workflow is required.

If source URLs become clickable, render links directly rather than server-side redirect endpoints.

---

### T-15 Authentication Bypass

**Applicability:** NOT APPLICABLE to current MVP

Reason:
No authentication exists.

Revisit before adding accounts.

---

### T-16 Authorization Bypass

**Applicability:** NOT APPLICABLE to current MVP

Reason:
No role/permission model exists.

Revisit before adding accounts/admin features.

---

### T-17 Privilege Escalation

**Applicability:** NOT APPLICABLE to runtime MVP

Reason:
No user privilege levels.

Development privilege risks remain relevant through GitHub/CI.

---

### T-18 Session / Token Weaknesses

**Applicability:** NOT APPLICABLE

Reason:
No login/session tokens.

API/provider secrets remain relevant and are handled separately.

---

### T-19 Webhook Spoofing

**Applicability:** NOT APPLICABLE

Reason:
No webhook endpoint exists.

Revisit if webhooks are added.

---

### T-20 Replay Attacks

**Applicability:** LOW

Reason:
Recommendation requests are read-oriented and have no irreversible business outcome.

Rate abuse remains applicable.

---

### T-21 Provider Impersonation / MITM

**Applicability:** REQUIRED/APPLICABLE

Risk:
External provider traffic could be intercepted or redirected.

Controls:

- HTTPS only
- standard TLS validation
- fixed provider base URL
- no user-controlled provider endpoint

---

### T-22 Secrets Exposure

**Applicability:** CRITICAL

Assets:

- LLM API key
- RecipeAPI.io API key
- deployment secrets

Controls:

- environment variables
- secret stores
- `.env` excluded from Git
- `.env.example` contains names only
- no secrets in logs
- no secrets in frontend bundle
- secret scanning in CI where practical

---

### T-23 PII Exposure

**Applicability:** LOW

Reason:
No intended PII is collected.

Controls:

- minimal logging
- no unnecessary persistence
- reassess if accounts are introduced

---

### T-24 Resource Exhaustion / Application DoS

**Applicability:** REQUIRED/APPLICABLE

Risks:

- very large ingredient lists
- repeated recommendation calls
- agent loops
- deep pagination
- excessive provider calls
- expensive LLM calls

Controls:

- request limits
- maximum ingredient count
- bounded search attempts
- bounded candidates
- bounded provider calls
- timeout
- deployment rate limiting where practical

---

### T-25 Request Smuggling

**Applicability:** CONDITIONAL / INFRASTRUCTURE DEPENDENT

Reason:
Primarily handled by hosting/proxy stack.

Controls:

- standard supported deployment platform
- avoid custom HTTP proxy implementation
- keep dependencies updated

---

### T-26 Unsafe File / Media Handling

**Applicability:** LOW

Reason:
No user uploads.

Recipe images are external URLs, not uploaded files.

Controls:

- do not proxy arbitrary user-supplied media
- validate/render source URLs safely

---

### T-27 Supply Chain / Dependency Risk

**Applicability:** REQUIRED/APPLICABLE

Risks:

- malicious npm/Python dependency
- compromised package
- vulnerable library

Controls:

- minimal dependency set
- lock versions where practical
- dependency scanning
- review unexpected new packages
- Claude may not add major dependencies without justification

---

### T-28 CI/CD Compromise

**Applicability:** REQUIRED/APPLICABLE

Risks:

- malicious workflow change
- leaked repository secrets
- unsafe PR scripts
- unauthorized deployment

Controls:

- Founder merge authority
- review CI changes carefully
- least-privilege GitHub secrets
- no secrets printed in CI logs
- protect main branch where possible

---

### T-29 Prompt Injection from User Input

**Applicability:** CRITICAL

Risk:
Ingredient or preference text attempts to override system instructions.

Controls:

- user input treated as data
- system policy higher priority
- allow-listed tools
- schema validation
- no arbitrary tool access
- no system secret disclosure

---

### T-30 Prompt Injection from RecipeAPI.io Content

**Applicability:** CRITICAL

Risk:
Recipe names/descriptions/instructions contain instruction-like malicious text.

Controls:

- external recipe content explicitly marked untrusted
- tool outputs treated as data
- agent system rules prohibit following instructions inside provider content
- deterministic rendering from validated DTO fields

---

### T-31 LLM Tool Abuse

**Applicability:** CRITICAL

Risk:
Model attempts unsupported actions or malformed tool calls.

Controls:

- tool allow-list
- strict schemas
- bounded corrective retry
- reject unknown IDs
- reject arbitrary URLs
- no shell/code execution tools

---

### T-32 LLM Hallucination

**Applicability:** CRITICAL

Risk:
Model invents recipe, price, score, ingredient, or provider result.

Controls:

- final recommendations must reference grounded Recipe DTO
- calculations deterministic
- unknown values remain unknown
- tool outputs authoritative
- tests for hallucinated IDs

---

### T-33 Provider Data Poisoning / Bad Data

**Applicability:** REQUIRED/APPLICABLE

Risk:
External provider returns malformed or misleading values.

Controls:

- schema validation
- sanity checks
- reject malformed recipe
- no medical/allergy guarantees
- provider tags not treated as authoritative safety claims

---

### T-34 Cache Poisoning / Stale Data

**Applicability:** REQUIRED/APPLICABLE

Controls:

- source identity retained
- cache key structured
- stale flag/TTL
- invalid cache rejected
- cache cannot overwrite authoritative local datasets

---

### T-35 Local Dataset Tampering

**Applicability:** REQUIRED/APPLICABLE

Risk:
Curated recipes or price data modified without governance.

Controls:

- repository-controlled source
- Git history
- PR review
- validation scripts
- provenance requirements

---

## 8. Highest-Priority MVP Threats

The highest-priority threats for the competition MVP are:

1. Secrets exposure
2. Prompt injection
3. LLM tool abuse
4. LLM hallucination
5. API/resource abuse
6. External provider malformed data
7. XSS from external text
8. SSRF through arbitrary URL behavior
9. Dependency/supply-chain risk
10. Governance bypass in development

---

## 9. Security Testing Expectations

At minimum test:

- oversized user input
- script-like ingredient text
- prompt injection in user input
- prompt injection in recipe content
- malformed tool args
- nonexistent recipe ID
- arbitrary URL attempt
- missing secret behavior
- provider malformed response
- rate-limit/429 handling
- raw HTML not rendered
- secrets absent from frontend build

---

## 10. Residual Risk

The MVP remains dependent on external:

- LLM provider
- RecipeAPI.io
- deployment platform

No design can eliminate those dependencies entirely.

Residual risk is accepted only within the bounded competition scope and must remain visible in:

- security acceptance matrix
- remediation register
- release checklist

---

## 11. Threat Model Change Triggers

This document must be reviewed before adding:

- authentication
- accounts
- admin interface
- payments
- ordering
- file upload
- image recognition
- arbitrary URL fetch
- webhooks
- queues
- background workers
- user history
- persistent personal data
- multi-tenancy
- new external providers
