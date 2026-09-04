# PantryPilot Migration and Release Policy

## 1. Purpose

This document defines how PantryPilot handles:

- database schema changes
- seed/reference data changes
- configuration changes
- release preparation
- deployment verification
- rollback
- release tagging

The goal is to make deployment changes deliberate, traceable, and reversible where practical.

---

## 2. Scope

This policy applies to:

- SQLite schema changes
- local curated recipe data
- grocery price reference data
- cache schema/data format
- environment variables
- provider configuration
- backend/frontend release packaging
- deployment configuration

---

## 3. Current MVP Context

PantryPilot competition MVP uses:

- React + Vite frontend
- FastAPI backend
- SQLite
- RecipeAPI.io
- local curated recipe provider
- local reference price data

There is currently:

- no multi-tenant database
- no user account migration
- no distributed database cluster
- no event bus
- no queue migration
- no payment migration

Do not add enterprise migration tooling unless actual project complexity requires it.

---

## 4. Migration Principle

Any persistent-data structure change must be intentional.

Do not silently modify SQLite schema from application runtime logic without an authorized migration/change mechanism.

Every schema change must identify:

- old state
- new state
- compatibility impact
- migration method
- rollback or recovery method
- test evidence

---

## 5. SQLite Schema Changes

A schema change includes:

- adding table
- removing table
- adding column
- removing column
- changing type/meaning
- changing constraint
- changing unique key
- changing foreign key
- changing index used for integrity/performance

Every schema change requires:

1. authorized ticket
2. schema diff
3. migration/rebuild plan
4. test against representative existing data
5. rollback/recovery note
6. PR review

---

## 6. Destructive Changes

Destructive changes include:

- dropping tables
- dropping columns
- deleting reference data
- changing canonical IDs
- changing unique identity rules
- rewriting persisted meaning

These require explicit Founder / Product Owner approval before merge.

Where practical:

- export backup first
- use copy/transform/replace approach
- verify record counts
- verify integrity after migration

---

## 7. Canonical Ingredient Migration

Canonical ingredient IDs are domain identifiers.

Changing a canonical ingredient ID can affect:

- pantry matching
- price lookup
- recipe ingredient mapping
- cache records
- tests
- local curated recipes

Therefore canonical ID changes must not be treated as simple text edits.

Any such change must include:

- alias impact analysis
- dependent-record update
- regression tests
- escape-path review

---

## 8. Local Curated Recipe Data Changes

Local curated recipe data is approved grounded content.

Changes must preserve:

- source identity
- provenance
- ingredient structure
- recipe ID uniqueness
- required fields
- data validity

Do not overwrite recipe IDs in a way that makes old references point to different recipes.

Material recipe-content changes should be traceable through Git history.

---

## 9. Price Reference Data Changes

Grocery price reference data may be refreshed without changing application code.

A refresh must record, where practical:

- source
- capture/import date
- package quantity
- package unit
- package price
- normalized unit price where safe
- source URL/reference

Unknown values must remain unknown.

Do not convert missing values to zero during import.

---

## 10. Data Import Safety

Any import script must validate:

- required columns/fields
- canonical IDs
- duplicate keys
- invalid numeric values
- negative prices
- invalid quantities
- unsupported units
- missing provenance where required

Imports should fail clearly rather than partially corrupt authoritative data.

---

## 11. Backup Before Migration

Before a migration that can alter persisted data:

create a recoverable copy of the relevant SQLite database or data file.

For competition MVP, a timestamped file copy is sufficient if it is reliable and documented.

Do not commit secrets or unsafe runtime databases to Git merely to create a backup.

---

## 12. Migration Idempotency

Where a migration script may be run more than once, it must either:

- be safely idempotent
- detect already-applied state
- fail clearly before causing duplication

Repeated execution must not silently duplicate reference records.

---

## 13. Configuration Changes

A release-impacting configuration change includes:

- API endpoint/base URL
- provider model
- timeout
- retry limit
- candidate limit
- search attempt limit
- CORS origin
- environment variable
- deployment port
- database path

Configuration changes must follow the same ticket/review process as code when they affect behavior.

---

## 14. Secrets

Secrets must not be stored in:

- repository files
- committed `.env`
- frontend source
- frontend bundles
- migration logs
- test fixtures

Use environment variables or deployment secret configuration.

---

## 15. Backward Compatibility

For competition MVP, long-term API backward compatibility is not mandatory before first public release.

However:

- frontend and backend in the same release must use matching contracts
- database/data formats must match the deployed code
- breaking changes must not be hidden inside unrelated tickets

After a stable public API is declared, use explicit versioning for breaking API changes.

---

## 16. Release Candidate

A release candidate should be created only when:

- required implementation is merged
- blocking decisions are resolved
- critical tests pass
- release-blocking findings are resolved or explicitly accepted
- database/data build is verified
- environment configuration is known
- deployment target is known

---

## 17. Release Checklist

Before competition release, verify:

- frontend production build succeeds
- backend starts successfully
- health endpoint responds
- SQLite database opens
- required tables/data exist
- RecipeAPI.io credentials are configured
- RecipeAPI.io live smoke test passes
- LLM provider credential/config works
- local curated recipes load
- price reference data loads
- recommendation smoke path works
- failure path is usable
- no secrets are exposed
- critical test suite passes
- deployment URL works
- known-good release commit is identified

---

## 18. Release Tagging

For major competition-ready releases, create a Git tag.

Suggested format:

`v0.1.0-competition`

or:

`v1.0.0`

depending on project maturity.

Tag only a commit that has passed the required release gate.

Do not tag arbitrary development commits as release-ready.

---

## 19. Release Evidence

Record at minimum:

- commit SHA
- tag
- deployment URL
- release date
- test result/reference
- unresolved accepted risks
- relevant gate approval

The evidence may be kept in repository documentation or release notes.

---

## 20. Deployment Verification

After deployment:

verify the deployed system, not only the local build.

Perform smoke checks for:

- frontend load
- API connectivity
- health endpoint
- recommendation request
- RecipeAPI call
- LLM/tool path
- local curated source
- price lookup
- error handling

A successful CI build does not prove production deployment works.

---

## 21. Rollback Principle

If the deployed release has a serious regression:

prefer rollback to the most recent known-good version rather than emergency uncontrolled changes.

Rollback may include:

- previous application commit/tag
- previous database copy
- previous data files
- previous environment configuration

The exact method depends on the selected deployment platform.

---

## 22. Failed Migration

If a migration fails:

1. stop further writes where practical
2. inspect actual state
3. restore known-good backup if required
4. determine root cause
5. record finding if material
6. correct via authorized ticket
7. re-run tests
8. retry only after verification

Do not blindly re-run a partially destructive migration.

---

## 23. Emergency Fixes

Competition timing may require urgent fixes.

Emergency does not mean ungoverned.

At minimum an emergency fix still requires:

- clearly identified defect
- bounded change
- test or explicit manual verification
- independent review where time permits
- Founder approval
- repository history

After release pressure passes, any skipped documentation must be reconciled.

---

## 24. Release Blocking Conditions

Release must be blocked for:

- known secret exposure
- uncontrolled recipe generation
- ability for LLM to bypass deterministic constraints
- corrupted/invalid reference data
- unresolved critical security issue
- broken primary recommendation path
- broken provider credentials/configuration
- uncontrolled outbound URL behavior
- unbounded retry/pagination capable of exhausting quota
- deployment that cannot complete a smoke test

---

## 25. Accepted Risk

A non-critical issue may be released only when:

- impact is understood
- scope is bounded
- workaround exists where needed
- remediation is recorded
- Founder / Product Owner explicitly accepts the risk

Risk acceptance must not silently convert a failing critical control into “release ready.”

---

## 26. Post-Release Reconciliation

After release:

update where applicable:

- `CURRENT_STATUS.md`
- `APPROVAL_GATES.md`
- `PROJECT_HISTORY.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/MASTER_REMEDIATION_REGISTER.md`

Repository status must reflect what was actually released.

---

## 27. Competition-Speed Rule

For PantryPilot MVP:

keep migration and release controls simple.

Prefer:

- small SQL/data scripts
- explicit backups
- deterministic validation
- clear release checklist
- Git tags
- smoke tests

Avoid introducing heavyweight release infrastructure that does not materially reduce project risk.
