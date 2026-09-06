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

---

## DEC-013 — Grocery Price Ingestion and Reference Pricing Policy

**Status:** APPROVED  
**Decision:** LuLu Hypermarket UAE is the primary competition grocery pricing source (Carrefour is no longer the PP-003 baseline). The following ingestion/pricing rules are approved:

- **Current price:** `price` is the sole input to reference-price generation and cost calculations. `retailPrice`, `discountAmount`, and `discountRatio` are provenance/audit metadata only and never affect cost calculation.
- **Reference price:** for multiple valid products mapped to the same canonical ingredient and compatible normalized unit, use the **median normalized unit price** (one contributor → that value; odd count → middle value; even count → arithmetic mean of the two middle values). Contributors with incompatible unit dimensions for the same canonical ID are never combined — the data-quality issue is reported and no reference row is promoted for that canonical ID until resolved.
- **Brand:** LuLu's `brand` field is preserved as provenance; brand never defines canonical identity; multiple brands may contribute to one canonical ingredient; a null brand never blocks ingestion.
- **Canonical naming:** canonical IDs represent ingredients, not brands or packages. Meaningful cut/species/form distinctions are preserved (e.g. `boneless_chicken_breast` vs `chicken_wings`; `salmon_fillet` vs `whole_salmon`). Marketing terms (premium/fresh/local/value-pack) are not encoded. Branded prepared spice mixtures (e.g. biryani/chicken masala) get their own canonical IDs and are never collapsed into component spices.
- **Package/unit parsing:** LuLu's `content` field is the primary package-size source. Deterministic parsing supports g, kg, ml, L/litre/litres, pieces/pcs, and multipacks (`N x size unit`). Mass and volume units are normalized to a common base (g, ml respectively). No mass/volume conversion is invented for bunch, pkt/packet, slices, teabags, or other non-metric package/count units.
- **Gallons:** never silently converted to litres (no authoritative UAE gallon-to-litre conversion rule is defined in this project). Gallon-denominated rows are retained in staging/mapped data but never promoted to a litre-normalized reference. This does not block PP-003.
- **Missing/ambiguous packages:** unresolved source rows are kept in staging and never promoted merely for being the only candidate for a canonical ingredient. Exception: a product whose source data explicitly states a reliable piece/count basis (e.g. "6 pcs") may be promoted on that basis. Package size and per-unit precision are never invented.
- **Manual curated fallback:** a small, explicitly reviewed manual/curated price entry mechanism exists for important ingredients LuLu's export doesn't usefully cover. Every manual entry requires a canonical ID, package/unit basis, AED price, and a provenance/source note, and is tagged with a source type distinct from LuLu-derived entries. This mechanism ships empty — PP-003 does not pre-populate synthetic pricing data.

**Rationale:** Prevents fabricated precision, brand-driven identity fragmentation, and silent unit-conversion errors in the grocery pricing pipeline, while keeping the architecture provider-neutral enough to support another offline source later without unnecessary generalized scraping infrastructure.  
**Owner:** Solution Architecture  
**Approver:** Founder / Product Owner  
**Blocking Scope:** Grocery pricing ingestion (M14), reference price repository (M10), cost engine (M11)  
**Required By:** Before PP-003 implementation (satisfied)  
**Subsequent Status:** Active
