# Module F Security Report — Security, Persistence, and Production Hardening

**Ticket:** `MODULE-F` (`docs/traceability/tickets/MODULE_F_SECURITY_PERSISTENCE.json`)
**Branch:** `feature/module-f-security-persistence`
**Date:** 2026-09-09
**Status:** Implementation complete, awaiting Founder review and browser acceptance (see checklist in the PR).

This report does not contain secrets, credentials, or sensitive values. It documents controls and their evidence, not the values they protect.

---

## 1. Threat Surface

PantryPilot's public-facing surface for a competition deployment is:

- `POST /api/recommend` — triggers LLM (Anthropic) usage and RecipeAPI.io usage per request; the highest-cost, highest-abuse-value endpoint.
- `GET /api/ingredients/suggest` — local, deterministic autocomplete; no external API cost, but still a public unauthenticated endpoint.
- `GET /api/health` — process/DB health only.
- Frontend static assets — served separately (build artifact), no server-side rendering.
- Browser `localStorage` — new in Module F; per-browser, never transmitted to the server, never shared across devices/users.

There are no accounts, no authentication, and no server-side persisted user data. The threat model is therefore: an anonymous public client abusing the API (cost/availability), a malicious or malformed upstream provider response, adversarial content embedded in pantry input or provider recipe data reaching the LLM, and browser-local data handling on the client.

---

## 2. Implemented Controls

### 2.1 Already in place before Module F (reconfirmed, not modified)

| Control | Evidence |
|---|---|
| Public request input validation and bounds | `backend/app/schemas/recommend.py` (`extra="forbid"`, bounded ingredients/exclusions/budget/servings/time/cuisine); `backend/tests/integration/test_recommend_endpoint.py` |
| CORS configured via environment, safe default (no wildcard) | `backend/app/config.py` `Settings.allowed_origins` |
| Secrets server-side only | `SecretStr` fields in `backend/app/config.py`; `.env`/`.env.local` gitignored; `backend/.env.example` is placeholder-only |
| Sanitized error responses (no traceback/secret/path leakage) | `backend/app/domain/errors.py` `PantryPilotError.to_error_envelope()`; generic 500 for unhandled exceptions |
| Prompt/tool injection boundaries | `backend/app/agent/policy.py`, `backend/app/integrations/llm_provider.py` (observation payload labeled `UNTRUSTED_STRUCTURED_DATA`, isolated from `SYSTEM_POLICY`); extensive existing test coverage in `backend/tests/agent/` |
| URL safety (no SSRF, no unsafe frontend link rendering) | Fixed `BASE_URL` constant in `backend/app/integrations/recipeapi_io.py`; `frontend/src/utils/safeUrl.js` rejects non-http(s) schemes, used for image/source URL rendering with `rel="noreferrer"` |
| Minimal health endpoint | `GET /api/health` — checks DB reachability only; never calls Anthropic or RecipeAPI.io; never exposes secret values |
| Environment-configurable frontend API origin | `VITE_API_BASE_URL` |
| Accessibility (ARIA combobox autocomplete, modal focus trap) | `frontend/src/components/IngredientAutocomplete.jsx`, `frontend/src/components/RecipeDetail.jsx` |

### 2.2 New in Module F

| Control | Implementation | Tests |
|---|---|---|
| Request body size limit | `backend/app/middleware/request_size_limit.py` — raw ASGI middleware, 16 KiB default cap, enforced against `Content-Length` up front and against actual streamed bytes independently (so a missing/understated `Content-Length` cannot bypass it); rejects with 413 before Pydantic validation or any agent/provider call | `backend/tests/unit/test_request_size_limit_middleware.py`, `backend/tests/integration/test_request_size_limit_endpoint.py` |
| Per-client rate limiting | `backend/app/rate_limit.py` — `slowapi`, in-memory, keyed by client IP. `/api/recommend`: 10/minute. `/api/ingredients/suggest`: 60/minute. Both configurable via `RATE_LIMIT_RECOMMEND` / `RATE_LIMIT_INGREDIENTS_SUGGEST`. 429 responses reuse the existing error-envelope shape and occur before any provider/LLM call | `backend/tests/integration/test_rate_limiting.py` (asserts no downstream provider/LLM call occurs once rejected) |
| CORS wildcard rejected at startup | `backend/app/config.py` — `ALLOWED_ORIGINS` containing `*` now fails fast at startup instead of silently producing a broken (and, combined with `allow_credentials=True`, non-functional) CORS configuration | `backend/tests/unit/test_config.py` |
| Structured request logging | `backend/app/middleware/request_logging.py` + `backend/app/logging_config.py` — logs request id, method, path, status, latency, high-level failure category only; never headers, bodies, or query strings. Query strings are deliberately excluded even for the low-sensitivity autocomplete `q=` text — see Section 4 (deployment assumption re: uvicorn access logging) | `backend/tests/unit/test_request_logging_middleware.py` |
| Adversarial-content regression test (prompt/tool injection) | New end-to-end test pushing an instruction-shaped string through the real observation-building path, confirming it stays inert untrusted data | `backend/tests/agent/test_orchestrator_scenarios.py` |
| Dependency scanning wired into CI | `pip-audit` (backend), `npm audit` (frontend) | `.github/workflows/ci.yml` `security` job |
| Secret-pattern scanning wired into CI | `scripts/scan_secrets.py` — pattern-based scan of all git-tracked files (cloud key formats, PEM headers, assigned opaque-secret literals); explicit, reviewed allow-listing via a trailing `# secret-scan: allow` comment | `.github/workflows/ci.yml` `security` job |
| Local browser persistence (pantry, prefs, history, saved recipes) | `frontend/src/utils/storage.js` (versioned, namespaced, fail-safe `localStorage` wrapper) | `frontend/src/utils/storage.test.js`, `frontend/src/hooks/useRecentSearches.test.jsx`, `frontend/src/hooks/useSavedRecipes.test.jsx`, `frontend/src/App.test.jsx` |
| Production UX hardening (non-technical error copy) | `frontend/src/services/api.js` — dedicated friendly copy for rate-limit (429) and network/offline failures, distinct from generic errors | `frontend/src/services/api.test.js` |

---

## 3. Known Limitations

- **In-memory rate limiting.** `slowapi`'s default in-memory storage resets on process restart and is not shared across multiple worker processes/instances. This is an accepted, documented limitation for a single-VM, single-process competition deployment. If PantryPilot is ever scaled to more than one process, a shared limiter backend (e.g. `slowapi`'s Redis storage option) becomes necessary for the rate limit to remain effective — deliberately not added now, per the ticket's instruction not to introduce Redis/a distributed system unless genuinely required.
- **Secret-pattern scan is pattern-based, not a full entropy/history scanner.** `scripts/scan_secrets.py` catches known key-shape patterns and PEM headers in the current tracked tree; it does not scan git history and is not a substitute for a dedicated tool (gitleaks/trufflehog) if deeper coverage is later wanted.
- **`pip-audit` PYSEC-2026-1845 (pytest).** See `docs/MASTER_REMEDIATION_REGISTER.md` MR-001. Dev/CI-only exposure, assessed as minimal; pending a Founder decision to take the major-version fix or formally accept the risk.
- **`REL-02` (worst-case ~15s latency target) remains unmeasured** — pre-existing gap, not addressed by Module F; noted here only because performance review is part of this ticket's self-review and this gap was already flagged in `docs/REQUIREMENTS_TRACEABILITY.md` before Module F started.

---

## 4. Deployment Assumptions (for the eventual Oracle Cloud deployment — not part of Module F)

- Production must run uvicorn with access logging disabled (e.g. `--no-access-log`, or an equivalent `log_config`) so that PantryPilot's own structured `RequestLoggingMiddleware` — which deliberately excludes query strings — is the sole HTTP-level request log. Without this, uvicorn's default access log (which does include the full request line/query string) would still record autocomplete search text.
- `ALLOWED_ORIGINS` must be set to the exact production frontend origin(s) at deploy time; the application now fails fast at startup if this is misconfigured as `*`.
- `MAX_REQUEST_BODY_BYTES`, `RATE_LIMIT_RECOMMEND`, and `RATE_LIMIT_INGREDIENTS_SUGGEST` have sensible defaults (16 KiB / 10 per minute / 60 per minute) but are environment-overridable if production traffic patterns require adjustment.
- Deployment itself (Nginx, systemd, Docker, TLS, Oracle networking) is explicitly out of scope for Module F and remains a separate, later phase.

---

## 5. Deliberately Accepted / Deferred Items for Competition Scope

Nothing in this ticket was unilaterally marked as Founder-accepted risk — per `docs/SECURITY_ACCEPTANCE_MATRIX.md` Section 4, Claude Code does not have that authority. The one open item (MR-001, pytest advisory) is recorded as `OPEN` in `docs/MASTER_REMEDIATION_REGISTER.md`, pending an explicit Founder decision.

Scope deliberately excluded per the ticket (not implemented, not evaluated further here): authentication, user accounts, cloud/server-side persistence, payments, social sharing, meal plans, nutrition generation, grocery ordering, retailer integrations, push notifications, mobile app, deployment infrastructure.
