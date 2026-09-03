# PantryPilot Decision Register

This file records project, architecture, provider, security, data, deployment, and governance decisions.

Approved decisions must not be rewritten later. If circumstances change, append a new subsequent status or create a superseding decision.

---

## DEC-001 — Recipe Generation Policy

**Status:** APPROVED  
**Decision:** PantryPilot will never generate, invent, or rewrite recipes using the LLM.  
**Selected Approach:** Existing grounded recipes only.  
**Rationale:** Keeps the application grounded, reliable, explainable, and focused on agentic decision-making rather than content generation.  
**Owner:** Founder / Product Owner  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Entire application  
**Required By:** Before implementation  
**Subsequent Status:** Active

---

## DEC-002 — Primary Recipe Source

**Status:** APPROVED  
**Decision:** RecipeAPI.io is the primary live recipe source.  
**Rationale:** August feasibility testing showed sufficient structured recipe data and useful search capability for PantryPilot.  
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Recipe integration  
**Required By:** Before provider implementation  
**Subsequent Status:** Active

---

## DEC-003 — Regional Recipe Coverage

**Status:** APPROVED  
**Decision:** Use a small read-only local curated recipe provider for approved Indian/Pakistani/desi coverage gaps.  
**Rationale:** RecipeAPI.io testing showed weak coverage for several desi dish searches.  
**Constraints:**
- No LLM-generated recipe content
- Read-only at runtime
- Same internal Recipe DTO as RecipeAPI.io
- Provenance required
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Regional recipe routing  
**Required By:** Before local provider implementation  
**Subsequent Status:** Active

---

## DEC-004 — TheMealDB

**Status:** CLOSED  
**Decision:** TheMealDB is not part of the PantryPilot MVP.  
**Rationale:** Removing it reduces integration and testing complexity.  
**Owner:** Founder / Product Owner  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Recipe provider architecture  
**Subsequent Status:** Removed from MVP

---

## DEC-005 — Agent Architecture

**Status:** APPROVED  
**Decision:** Use a single LLM agent with direct tool/function calling and bounded autonomous retry/replan behavior.  
**Rationale:** Provides real agency with lower complexity than a multi-agent system or orchestration framework.  
**Constraints:**
- LLM controls search/retry/stop decisions
- Python controls deterministic calculations
- Maximum bounded attempts
- No hidden fixed workflow disguised as agency
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Agent implementation  
**Required By:** Before agent coding  
**Subsequent Status:** Active

---

## DEC-006 — Deterministic Business Logic

**Status:** APPROVED  
**Decision:** Ingredient normalization, pantry matching, price lookup, cost calculation, hard constraints, and ranking are handled by deterministic Python tools.  
**Rationale:** Prevents hallucinated arithmetic and makes outputs testable and explainable.  
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Core recommendation engine  
**Subsequent Status:** Active

---

## DEC-007 — Price Data Strategy

**Status:** APPROVED  
**Decision:** Use one-time UAE grocery data acquisition and normalize the result into a local SQLite reference-price database.  
**Constraints:**
- No runtime grocery scraping
- Pricing is reference pricing, not live pricing
- Unknown price is never treated as zero
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Cost engine  
**Subsequent Status:** Active

---

## DEC-008 — Application Stack

**Status:** APPROVED  
**Decision:**
- Frontend: React + Vite
- Backend: Python 3.11+ + FastAPI
- Database: SQLite
- Version control: Git + GitHub
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Repository/application foundation  
**Subsequent Status:** Active

---

## DEC-009 — Coding Workflow

**Status:** APPROVED  
**Decision:** Claude Code acts as implementation agent. ChatGPT acts as solution architect and independent reviewer. Founder remains final merge authority.  
**Rationale:** Separates architecture/review from implementation.  
**Constraints:**
- Claude never merges
- Claude works only on authorized ticket/branch
- ChatGPT reviews actual diff/code/tests
- Founder performs final merge
**Owner:** Founder / Product Owner  
**Approver:** Founder / Product Owner  
**Subsequent Status:** Active

---

## DEC-010 — Open: Competition LLM Model

**Status:** OPEN  
**Question:** Which exact production model will power the PantryPilot agent during the competition?  
**Current Candidate:** Claude Sonnet 5  
**Required By:** Before M03 Agent Orchestrator implementation  
**Blocking Scope:** Agent runtime configuration  
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner

---

## DEC-011 — Open: Deployment Platform

**Status:** OPEN  
**Question:** Which hosting platform will be used for the final competition deployment?  
**Required By:** Before production deployment work  
**Blocking Scope:** Deployment only  
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner

---

## DEC-012 — Open: Local Curated Recipe Dataset Size

**Status:** OPEN  
**Question:** Final number and exact approved recipes for the local desi recipe provider.  
**Current Direction:** Approximately 20–40 recipes.  
**Required By:** Before local curated provider is considered complete  
**Blocking Scope:** Local recipe provider completeness  
**Owner:** Founder / Product Owner  
**Approver:** Founder / Product Owner
