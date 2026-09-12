# PantryPilot Admin Dashboard

Branch: `feature/admin-ingredient-dashboard`. Not merged, not deployed. Founder review required before either.

## 1. Architecture

The admin dashboard is additive to the existing PantryPilot application, not a second application:

- **Database:** the same SQLite file the public app already uses (`settings.price_db_path`, default `data/pantrypilot.db`). No parallel database was created. Three new tables were added (`canonical_ingredients`, `admin_sessions`, `admin_audit_log`); the pre-existing but previously-unused `ingredient_aliases` table is now actually read/written; `manual_price_entries` and `ingredient_aliases` each gained an additive `active`/`updated_at`/`updated_by` column. See `backend/app/db/admin_schema.py` for the exact, idempotent migration.
- **Backend:** new routers under `backend/app/api/admin_*.py`, mounted at `/api/admin/...`, alongside (not replacing) the existing `/api/recommend` and `/api/ingredients/suggest` routers in `backend/app/main.py`.
- **Frontend:** a second root component (`frontend/src/admin/AdminApp.jsx`) that mounts instead of the public `App.jsx` only when the browser path starts with `/admin` (`frontend/src/main.jsx`). Same build, same bundle, no new framework, no router library — consistent with the existing `App.jsx` internal-state view-switching convention.

### Important architecture boundary — read this before editing ingredients or aliases

The **live** pantry-matching/autocomplete/normalization code (`backend/app/domain/ingredient_normalizer.py`, `backend/app/domain/ingredient_autocomplete.py`) does **not** read canonical ingredients or aliases from the database. It reads two disconnected Python module-level constants (`app.domain.canonical_ingredients` and `app.domain.grocery_taxonomy`). The `ingredient_aliases` DB table existed before this ticket but was never read by any runtime code path (verified by repo-wide grep).

Practical consequence: creating/editing a canonical ingredient or alias through this admin dashboard is fully real and persists correctly, and the dashboard reads its own writes back consistently — but it does **not** retroactively change what the live recommendation engine resolves a pantry ingredient to. Rewiring the normalizer/autocomplete to read from SQLite instead of the Python constants would be a real architecture change to Module A/B's frozen deterministic core (DEC-006) and was **not** authorized or made here.

**Pricing has no such gap.** `ingredient_prices` and `manual_price_entries` are already the exact tables `PriceRepository` reads at runtime (DEC-013), so admin price edits have immediate, real effect on the live cost engine. `ingredient_prices` (LuLu-derived, median-aggregated) is admin-*viewable only* — never hand-edited, to preserve its aggregation provenance invariants. `manual_price_entries` is the only table admin price writes go to, which is exactly what DEC-013 designed that table for.

## 2. Authentication / security model

- One controlled administrative account, configured entirely via environment (`PANTRYPILOT_ADMIN_USERNAME`, `PANTRYPILOT_ADMIN_PASSWORD_HASH`, `PANTRYPILOT_ADMIN_SESSION_SECRET`). No signup, no multi-user, no role management.
- Password hashing: stdlib `hashlib.scrypt` (memory-hard, salted, tunable-cost KDF). Neither Argon2id nor bcrypt is a current project dependency; rather than add one for a single-account login, this uses the stdlib primitive that already meets the security bar, keeping the project's existing minimal-dependency posture. See `backend/app/admin/security.py`.
- Sessions: a random session id is stored server-side in `admin_sessions` (SQLite), with `expires_at` and a nullable `revoked_at`. The browser cookie carries `session_id.HMAC-SHA256(session_id, PANTRYPILOT_ADMIN_SESSION_SECRET)` — HttpOnly, `SameSite=Strict`, `Path=/`, `Secure` when `ENVIRONMENT=production`. Explicit logout sets `revoked_at`, immediately invalidating the session everywhere (not just client-side).
- CSRF: double-submit style. The CSRF token is handed to the frontend only in the JSON body of `/admin/auth/login` and `/admin/auth/session` (never a second cookie, never localStorage) and is sent back as the `X-Admin-CSRF-Token` header on every POST/PATCH/DELETE. Verified against the session's own stored token with a constant-time comparison.
- Login rate limiting: `5/minute` per client IP (`rate_limit_admin_login`, reusing the existing `slowapi` infrastructure `app.rate_limit`), same mechanism as the public `/recommend` endpoint's rate limit.
- A bad username and a bad password return the exact same `401 ADMIN_UNAUTHORIZED` / "Invalid username or password" — never distinguishable.
- Every `/api/admin/*` route (except login) independently requires a valid, non-expired, non-revoked session via a FastAPI dependency (`app.admin.deps.require_admin_session` / `require_csrf`) — the frontend hiding `/admin` is never the only guard. Verified directly with `curl` against a live server (see §9).

## 3. New environment variables

| Variable | Required | Purpose |
|---|---|---|
| `PANTRYPILOT_ADMIN_USERNAME` | to enable admin | The one admin account's username |
| `PANTRYPILOT_ADMIN_PASSWORD_HASH` | to enable admin | Output of the hash-generation command below. Never the plaintext password. |
| `PANTRYPILOT_ADMIN_SESSION_SECRET` | to enable admin | Random secret used to sign session cookies |

Leaving any of the three unset disables `/api/admin/*` entirely — every route returns `503 ADMIN_NOT_CONFIGURED` rather than partially working. `.env.example` documents these (empty values, as with the existing secrets).

Generate the password hash:

```bash
cd backend
python scripts/hash_admin_password.py
```

Generate the session secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Never commit real values for any of the three.

## 4. Database migration

Additive and idempotent — safe to run against the existing production database, safe to run more than once, never drops or rewrites an existing row.

```bash
cd backend
python scripts/migrate_admin_schema.py --db data/pantrypilot.db
```

**Always back up first in production:**

```bash
cp /path/to/production/pantrypilot.db /path/to/backups/pantrypilot.db.$(date +%Y%m%d%H%M%S)
```

## 5. Admin API routes

All under `/api/admin`:

```
POST   /admin/auth/login
GET    /admin/auth/session
POST   /admin/auth/logout

GET    /admin/ingredients                          (search q=, status=, page=, page_size=)
POST   /admin/ingredients
GET    /admin/ingredients/{canonical_id}
PATCH  /admin/ingredients/{canonical_id}            (display_name, default_unit, status -- canonical_id is immutable)

GET    /admin/ingredients/{canonical_id}/aliases
POST   /admin/ingredients/{canonical_id}/aliases
PATCH  /admin/aliases/{alias}                       (explicit reassignment only, confirm_reassignment: true required)
DELETE /admin/aliases/{alias}                       (soft-deactivate, never a hard delete)

GET    /admin/ingredients/{canonical_id}/prices     (reference_prices read-only + manual_prices)
POST   /admin/ingredients/{canonical_id}/prices     (creates a manual_price_entries row)
PATCH  /admin/prices/{canonical_id}/{normalized_unit}
DELETE /admin/prices/{canonical_id}/{normalized_unit}  (soft-deactivate)

GET    /admin/audit                                 (entity_type=, page=, page_size=)
GET    /admin/dashboard/summary
GET    /admin/grocery/products                      (read-only, status=, q=, page=, page_size=)
```

## 6. Local startup

Backend:

```bash
cd backend
export PANTRYPILOT_ADMIN_USERNAME=founder
export PANTRYPILOT_ADMIN_PASSWORD_HASH=$(python scripts/hash_admin_password.py)   # prompts interactively; run separately and paste the printed hash instead in practice
export PANTRYPILOT_ADMIN_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python scripts/migrate_admin_schema.py --db data/pantrypilot.db
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

Local admin URL: **http://localhost:5174/admin** (or whatever port `npm run dev` prints — see `frontend/vite.config.js`).

## 7. Tests

```bash
cd backend && python -m pytest tests/admin tests/unit/test_admin_security.py -q   # admin-only: 74 tests
cd backend && python -m pytest -q                                                 # full backend suite: 727 tests

cd frontend && npx vitest run src/admin -q     # admin-only: 25 tests
cd frontend && npm test -- --run               # full frontend suite: 204 tests
```

## 8. Deployment (Oracle Ubuntu, Nginx, systemd) — prepare only, do not execute without Founder approval

1. **Pull validated `main`** (only after this branch is Founder-merged): `git pull origin main`
2. **Back up the production SQLite database:**
   ```bash
   cp /opt/pantrypilot/backend/data/pantrypilot.db /opt/pantrypilot/backups/pantrypilot.db.$(date +%Y%m%d%H%M%S)
   ```
3. **Configure admin secrets** in the production `backend/.env` (or systemd `EnvironmentFile`): `PANTRYPILOT_ADMIN_USERNAME`, `PANTRYPILOT_ADMIN_PASSWORD_HASH` (generated on a trusted machine via `python scripts/hash_admin_password.py`, never over an untrusted channel), `PANTRYPILOT_ADMIN_SESSION_SECRET`.
4. **Run the migration:**
   ```bash
   cd /opt/pantrypilot/backend
   .venv/bin/python scripts/migrate_admin_schema.py --db data/pantrypilot.db
   ```
5. **Build the frontend:**
   ```bash
   cd /opt/pantrypilot/frontend
   npm ci
   npm run build
   ```
6. **Restart the backend service:** `sudo systemctl restart pantrypilot-backend`
7. **Stage the frontend release** (new `dist/` directory alongside the current one — do not overwrite the live directory in place):
   ```bash
   sudo cp -r dist /opt/pantrypilot/frontend/releases/$(date +%Y%m%d%H%M%S)
   ```
8. **Switch the frontend release** (repoint Nginx's document root symlink to the new release directory, e.g. `sudo ln -sfn /opt/pantrypilot/frontend/releases/<new> /opt/pantrypilot/frontend/current`)
9. **Nginx:** ensure the SPA fallback applies to `/admin` too (`try_files $uri /index.html;` — the same rule already needed for the public app's client-side routes) and that `/api/admin/` proxies through the existing `/api/` proxy block unchanged. `sudo nginx -t && sudo systemctl reload nginx`
10. **Verify:**
    ```bash
    curl -s https://<host>/api/health
    curl -s -o /dev/null -w '%{http_code}\n' https://<host>/admin      # expect 200 (serves the SPA shell)
    curl -s -o /dev/null -w '%{http_code}\n' https://<host>/api/admin/ingredients   # expect 401 unauthenticated
    ```
11. **Public recipe smoke test:** submit one real search through the public UI and confirm results render, exactly as before this change.

## 9. Rollback

**Frontend:** repoint the Nginx symlink back to the previous release directory (`sudo ln -sfn .../releases/<previous> .../current`), reload Nginx. No data loss — release directories are kept, never overwritten in place.

**Backend:** `git checkout <previous-deployed-commit>` (or revert the merge), reinstall (`pip install .`), `sudo systemctl restart pantrypilot-backend`.

**Database:** the admin schema migration is purely additive (new tables + new nullable/defaulted columns) — the public app's existing tables and columns are untouched, so a backend/frontend rollback alone is safe without also reverting the database. Only restore the pre-migration backup if the migration itself is suspected of causing a problem:
```bash
sudo systemctl stop pantrypilot-backend
cp /opt/pantrypilot/backups/pantrypilot.db.<timestamp> /opt/pantrypilot/backend/data/pantrypilot.db
sudo systemctl start pantrypilot-backend
```
A failed or reverted admin deployment never requires touching the public app's own code path — the two are wired through fully independent routers, dependencies, and (for aliases/canonical ingredients) tables the public path doesn't read.

## 10. Credential rotation

1. Generate a new hash: `python scripts/hash_admin_password.py`
2. Update `PANTRYPILOT_ADMIN_PASSWORD_HASH` in production `.env` / systemd `EnvironmentFile`
3. `sudo systemctl restart pantrypilot-backend`
4. All existing sessions remain valid until they naturally expire (`admin_session_ttl_minutes`, default 60) — to force-invalidate every existing session immediately after a suspected credential compromise, also rotate `PANTRYPILOT_ADMIN_SESSION_SECRET` at the same time (a new secret makes every previously-issued cookie's signature invalid).

## 11. Known limitations

- Canonical ingredient / alias admin edits are administrative records only — they do not (yet) change live pantry-matching/autocomplete behavior. See §1.
- `manual_price_entries` writes are per-(canonical_id, normalized_unit) row; there is no bulk import/edit UI.
- Raw/mapped grocery product inspection (`/admin/grocery/products`) is read-only by design — no bulk remapping tool exists yet (ticket explicitly scoped this out for the first version).
- Rate limiting uses the existing in-memory `slowapi` storage (Module F's own documented limitation) — counters reset on process restart and are not shared across multiple worker processes.
- Single admin account only; no audit-log filtering by admin username (only by entity type) in this first version.

## 12. Incidental finding — unrelated to this ticket, flagged for the Founder

While live-testing this feature against a real `uvicorn` process (not just `TestClient`), a pre-existing bug was found in `backend/app/config.py`'s `allowed_origins` field: `pydantic-settings` attempts a JSON decode of any env-var-sourced value for a `list[str]`-typed field *before* the field's own `mode="before"` validator runs. A real `ALLOWED_ORIGINS=https://example.com` environment variable (the exact form the field's own validator is written to parse) crashes the app at startup with a `SettingsError`, because it is not valid JSON. This was never caught before because every existing unit test constructs `Settings(allowed_origins="...")` directly in Python, which bypasses the environment-variable parsing path entirely. **Not fixed here** (out of this ticket's authorized scope, and it touches public CORS configuration, not the admin dashboard) — recommend a small, separate, explicitly-authorized ticket.
