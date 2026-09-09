# PantryPilot Security Acceptance Matrix

## 1. Purpose

This document tracks security requirements by module/surface.

It distinguishes between:

- REQUIRED/APPLICABLE
- CONDITIONAL
- NOT APPLICABLE
- DEFERRED

It also tracks implementation maturity:

- DESIGNED
- FOUNDATION_IMPLEMENTED
- BUSINESS_PATH_IMPLEMENTED
- PROVIDER_GATED
- PILOT_BLOCKED
- PILOT_READY
- PRODUCTION_READY

A control is not considered complete simply because code exists.

---

## 2. Acceptance Matrix

| Surface / Module | Threat / Control | Applicability | Required Control | Current State | Required Tests / Evidence | Residual Risk / Future Trigger |
|---|---|---|---|---|---|---|
| Frontend | XSS from external recipe content | REQUIRED/APPLICABLE | React escaping, no raw HTML rendering | DESIGNED | frontend rendering test | Reassess if rich HTML is introduced |
| Frontend | Secret exposure | REQUIRED/APPLICABLE | No API keys in bundle/client config | DESIGNED | build inspection / secret scan | Reassess on deployment |
| Frontend | Oversized input | REQUIRED/APPLICABLE | Client-side limits plus backend enforcement | DESIGNED | negative input tests | Backend remains authoritative |
| Frontend (Local Browser Storage) | Saved user data (pantry, form prefs, recent-search history, saved recipes) | REQUIRED/APPLICABLE | Versioned, namespaced `localStorage` only; no server-side/cloud persistence; no accounts; storage bounded (history capped, no generated content stored); every read/write fails safe (never crashes on disabled/private-browsing storage) | BUSINESS_PATH_IMPLEMENTED | `frontend/src/utils/storage.test.js`, `frontend/src/hooks/useRecentSearches.test.jsx`, `frontend/src/hooks/useSavedRecipes.test.jsx`, `frontend/src/App.test.jsx` | Data is per-browser only (no cross-device/user sync, by design); a future schema change must bump the stored version rather than mutate the existing shape in place; revisit this row before any authentication/account/cloud-sync feature is added |
| API Layer | Request validation | REQUIRED/APPLICABLE | Pydantic validation and bounds | DESIGNED | API negative tests | None if maintained |
| API Layer | Rate/resource abuse | REQUIRED/APPLICABLE | bounded request body size; per-client-IP rate limiting on `/api/recommend` and `/api/ingredients/suggest` | BUSINESS_PATH_IMPLEMENTED | `backend/tests/unit/test_request_size_limit_middleware.py`, `backend/tests/integration/test_request_size_limit_endpoint.py`, `backend/tests/integration/test_rate_limiting.py` | In-memory limiter (`slowapi`) resets on process restart and is not shared across multiple worker processes/instances — acceptable for a single-VM competition deployment (see `docs/MODULE_F_SECURITY_REPORT.md`); revisit if PantryPilot scales beyond one process |
| API Layer | Authentication | NOT APPLICABLE | No accounts in MVP | DESIGNED | N/A | Revisit before accounts |
| API Layer | Authorization / tenant isolation | NOT APPLICABLE | No persisted tenant/user ownership | DESIGNED | N/A | Revisit before accounts or saved state |
| Agent Orchestrator | Prompt injection from user input | REQUIRED/APPLICABLE | system policy, user content treated as data | DESIGNED | prompt injection tests | Model behavior remains probabilistic |
| Agent Orchestrator | Prompt injection from recipe content | REQUIRED/APPLICABLE | provider content treated as untrusted data | DESIGNED | malicious provider fixture | Residual LLM risk remains bounded by tool controls |
| Agent Orchestrator | Tool abuse | REQUIRED/APPLICABLE | allow-listed tools and strict schemas | DESIGNED | malformed/unknown tool tests | Reassess if tools expand |
| Agent Orchestrator | Infinite loop / resource exhaustion | REQUIRED/APPLICABLE | bounded attempts, candidates, calls | DESIGNED | retry exhaustion tests | None within documented bounds |
| Agent Orchestrator | Hallucinated recipe | REQUIRED/APPLICABLE | source recipe ID grounding | DESIGNED | hallucination proof test | Model text must never become recipe authority |
| Agent Orchestrator | Hallucinated price / score | REQUIRED/APPLICABLE | deterministic Python authority | DESIGNED | deterministic tool tests | None if boundaries hold |
| Recipe Service | Provider-specific coupling | REQUIRED/APPLICABLE | provider-neutral interface | DESIGNED | contract tests | Reassess if provider added |
| RecipeAPI Adapter | SSRF | REQUIRED/APPLICABLE | fixed allow-listed provider base URL | DESIGNED | arbitrary URL rejection test | None if no arbitrary fetch added |
| RecipeAPI Adapter | Provider timeout | REQUIRED/APPLICABLE | explicit timeout | DESIGNED | timeout test | Provider availability remains external risk |
| RecipeAPI Adapter | 429 / retry storm | REQUIRED/APPLICABLE | bounded/no immediate repeated retry | DESIGNED | 429 test | Quota still external constraint |
| RecipeAPI Adapter | Malformed data | REQUIRED/APPLICABLE | schema validation and typed errors | DESIGNED | malformed payload test | External provider can still degrade |
| RecipeAPI Adapter | MITM/provider impersonation | REQUIRED/APPLICABLE | HTTPS/TLS, fixed endpoint | DESIGNED | config/code review | Relies on platform TLS |
| Local Curated Provider | Tampered recipe data | REQUIRED/APPLICABLE | repository-controlled source + provenance | DESIGNED | provenance and schema tests | Founder/review process remains important |
| Local Curated Provider | Generated recipe content | REQUIRED/APPLICABLE | explicit prohibition | DESIGNED | dataset review | Manual provenance review still needed |
| Ingredient Normalizer | Unsafe over-generalization | REQUIRED/APPLICABLE | UNKNOWN on ambiguous mapping | DESIGNED | ambiguity regression tests | Canonical vocabulary quality |
| Pantry Matcher | False match through unresolved data | REQUIRED/APPLICABLE | unresolved never silently counts as match | DESIGNED | matcher tests | None if invariant maintained |
| Price Repository | Missing price treated as zero | REQUIRED/APPLICABLE | explicit missing/incomplete state | DESIGNED | missing-price tests | Dataset coverage risk remains |
| Price Repository | SQL injection | REQUIRED/APPLICABLE | parameterized DB access | DESIGNED | repository tests | None if raw interpolation prohibited |
| Cost Engine | Incorrect budget precision | REQUIRED/APPLICABLE | Decimal-compatible handling | DESIGNED | threshold tests | None if implemented consistently |
| Ranker | LLM score override | REQUIRED/APPLICABLE | deterministic ranker only | DESIGNED | ranking tests | Architecture drift risk |
| SQLite | Foreign key / uniqueness integrity | REQUIRED/APPLICABLE | DB constraints where feasible | DESIGNED | real DB tests | SQLite feature/locking limits |
| SQLite | Concurrent corruption | CONDITIONAL | bounded writes and safe transactions | DESIGNED | targeted concurrency tests if writes added | Revisit if write volume grows |
| Cache | Poisoned/stale cache | REQUIRED/APPLICABLE | source identity + validation + TTL/state | DESIGNED | cache tests | Provider freshness limitations |
| Cache | Duplicate writes | REQUIRED/APPLICABLE | unique keys / safe upsert | DESIGNED | idempotency test | Low risk |
| Import Scripts | Path traversal | REQUIRED/APPLICABLE | fixed repo-controlled input paths | DESIGNED | path handling review | Reassess if user-provided files added |
| Import Scripts | Duplicate authoritative data | REQUIRED/APPLICABLE | repeatable/idempotent import | DESIGNED | repeated import test | Dataset quality remains |
| Logging | Secret exposure | REQUIRED/APPLICABLE | redaction / never log keys | BUSINESS_PATH_IMPLEMENTED | `backend/tests/unit/test_request_logging_middleware.py`; manual review of every `logger.*` call site (`app/middleware/request_logging.py`, `app/integrations/recipeapi_io.py`) confirms only request id/method/path/status/latency/failure-category or provider name/relative path/status/duration are logged — never headers, bodies, query strings, or the RecipeAPI key | Reassess if a new logger call site is added; `configure_logging()` now attaches a root handler for the first time, so any future log call anywhere in the app becomes actually visible in output |
| Logging | Hidden chain-of-thought | REQUIRED/APPLICABLE | log only high-level action labels | DESIGNED | logging review | None |
| GitHub / CI | Secret leakage | REQUIRED/APPLICABLE | secret scanning and least privilege | BUSINESS_PATH_IMPLEMENTED | `scripts/scan_secrets.py`, wired as the `security` CI job | Pattern-based scanner, not a full entropy/history scanner — revisit if a dedicated tool (gitleaks/trufflehog) is later warranted |
| GitHub / CI | Unauthorized merge | REQUIRED/APPLICABLE | Founder merge authority / branch protections where possible | DESIGNED | repo settings / process evidence | Human governance still required |
| Dependencies | Vulnerable dependency | REQUIRED/APPLICABLE | minimal deps + scanning | BUSINESS_PATH_IMPLEMENTED | `pip-audit` (backend, no ignored findings) and `npm audit` (frontend), wired as the `security` CI job | The one finding raised during Module F (pytest PYSEC-2026-1845/MR-001) was fixed, not accepted — `pytest`/`pytest-asyncio` upgraded to `>=9.0.3,<10`/`>=1.4,<2`; see `docs/MASTER_REMEDIATION_REGISTER.md` MR-001 (`RE_VERIFIED`). No unresolved finding remains. New vulnerabilities may still appear over time |
| Deployment | HTTPS | REQUIRED/APPLICABLE | TLS enabled | DESIGNED | deployed endpoint evidence | Depends on selected host |
| Deployment | CORS | REQUIRED/APPLICABLE | explicit production origins | DESIGNED | deployed config test | Open decision until host/frontend URL chosen |
| Deployment | Secret storage | REQUIRED/APPLICABLE | host secret store/env | DESIGNED | deployment evidence | Open until platform chosen |
| Deployment | Container security | NOT APPLICABLE currently | No container required | DESIGNED | N/A | Revisit if Docker introduced |
| Webhooks | Spoofing/replay | NOT APPLICABLE | No webhooks | DESIGNED | N/A | Revisit before webhook implementation |
| Payments | Payment security | NOT APPLICABLE | No payments | DESIGNED | N/A | Revisit if ordering/payment added |
| File Upload | Unsafe media/file handling | NOT APPLICABLE | No file uploads | DESIGNED | N/A | Revisit before uploads |
| Multi-tenancy | Tenant isolation | NOT APPLICABLE | No tenant model | DESIGNED | N/A | Must be redesigned before multi-user persisted state |

---

## 3. Security Release Conditions

PantryPilot must not be considered `PILOT_READY` or competition-release ready until:

- secrets are absent from Git
- secrets are absent from frontend build
- CORS is configured for deployment
- request bounds are enforced
- agent attempts/candidates/provider calls are bounded
- RecipeAPI timeout and 429 handling work
- prompt injection tests pass
- hallucinated recipe/source IDs are blocked
- raw HTML rendering is prohibited
- provider payloads are validated
- missing prices are not treated as zero
- critical DB constraints/tests pass
- dependency/security scans have no unresolved critical issue
- no unresolved CRITICAL/HIGH security finding remains without explicit accepted risk

---

## 4. Accepted-Risk Rule

Security findings may be accepted only by the Founder / Product Owner when:

- the risk is documented
- severity is documented
- mitigation is documented
- scope/time limitation is explicit
- future remediation trigger is recorded

The status must be:

`BOUNDED ACCEPTED RISK`

in the relevant decision/remediation record.

Claude Code may not accept security risk on behalf of the Founder.

ChatGPT may recommend risk acceptance but cannot make the final acceptance decision.

---

## 5. Change Triggers

This matrix must be revised before adding:

- authentication
- user accounts
- saved user data
- admin features
- new provider
- webhooks
- file uploads
- image recognition
- payments
- grocery ordering
- background workers
- queues
- multi-tenancy
- arbitrary URL retrieval
- richer HTML rendering

**Module F note:** local browser-only pantry/preferences/history/saved-recipe storage was added under this ticket. This is the "saved user data" trigger above — addressed by revising this matrix (see the new Local Browser Storage row in Section 2) rather than by adding accounts, a server-side user database, or any cross-device sync. Authentication/accounts/cloud persistence remain explicitly out of scope and would require a further revision of this matrix before implementation.
