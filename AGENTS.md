# PantryPilot Agent Instructions

## Canonical Agent Contract

The authoritative implementation-agent contract for PantryPilot is:

`docs/AGENTS.md`

All coding agents working in this repository MUST read and follow:

- `docs/AGENTS.md`
- `CLAUDE.md`
- `DECISION_REGISTER.md`
- `CURRENT_STATUS.md`
- `APPROVAL_GATES.md`
- `docs/AI_DELIVERY_OPERATING_MODEL.md`

before implementation begins.

---

## Mandatory Rules

1. No implementation without an authorized ticket.
2. Do not invent product, security, provider, architecture, or business decisions.
3. Stop when a required decision is unresolved.
4. Stay within the authorized branch and file scope.
5. Do not perform unrelated cleanup.
6. Do not merge pull requests.
7. Preserve deterministic business logic outside the LLM.
8. Preserve provider-neutral boundaries.
9. Add or update required tests.
10. Complete self-review before independent review.
11. Record confirmed findings in the Master Remediation Register.
12. GitHub repository state is authoritative.

If this file and `docs/AGENTS.md` ever appear inconsistent, `docs/AGENTS.md` is authoritative until the inconsistency is formally corrected.
