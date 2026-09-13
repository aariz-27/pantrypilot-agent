# PantryPilot

PantryPilot is an agentic recipe recommendation application that helps users decide what they can cook from the ingredients they already have, while considering preferences such as time, budget, servings, cuisine, and exclusions.

The system deliberately separates **AI reasoning** from **deterministic business logic**. The LLM helps plan the search, while Python code controls ingredient normalization, pantry matching, missing-item detection, pricing, constraint handling, grounding, and final ranking.

## What PantryPilot Does

A user provides pantry ingredients and optional preferences. PantryPilot then:

1. Normalizes the ingredient input.
2. Builds a grounded recipe-search strategy.
3. Queries a live recipe provider.
4. Evaluates returned recipes against pantry contents and user preferences.
5. Calculates missing ingredients and estimated additional cost where pricing is known.
6. Ranks grounded recipes using deterministic scoring.
7. Returns the strongest matches together with useful alternatives and clear deviation labels.

PantryPilot never relies on the LLM to invent recipe names, ingredients, quantities, prices, or ranking scores.

## Agentic Architecture

The LLM is used as a **planning agent**, not as the source of truth.

```text
User Input
   ↓
Ingredient Resolution / Normalization
   ↓
LLM Search Planning
   ↓
Recipe Provider Search
   ↓
Deterministic Candidate Evaluation
   ↓
Pantry Match + Missing Items + Cost Estimation
   ↓
Deterministic Ranking
   ↓
Grounded Recommendations
```

This design keeps the flexible reasoning benefits of an LLM while ensuring that critical decisions remain predictable, testable, and reproducible.

## Why Deterministic Logic Matters

LLMs are probabilistic and can hallucinate. PantryPilot therefore keeps important rules outside the model:

- **Ingredient ownership:** generic ingredients are not silently converted into specific variants.
- **Grounding:** only recipes returned by an approved recipe provider can be displayed.
- **Pricing:** unknown prices remain unknown and are never treated as zero.
- **Exclusions:** allergy/exclusion checks are deterministic.
- **Ranking:** recipe scores are calculated in Python using fixed weights.
- **Testing:** critical behavior can be verified with repeatable unit and integration tests.

## Ranking Model

The deterministic ranking model uses the following fixed weights:

| Factor | Weight |
|---|---:|
| Pantry coverage | 45% |
| Lower additional cost | 30% |
| Fewer missing ingredients | 15% |
| Cuisine preference | 10% |

Time, budget, servings, and cuisine preferences influence recommendation quality and grouping, while true safety and integrity rules remain hard constraints.

## Technology Stack

### Frontend
- React
- Vite
- JavaScript

### Backend
- Python
- FastAPI
- Pydantic v2
- Uvicorn

### Data
- SQLite
- Deterministic ingredient vocabulary and alias resolution
- Manual and reference ingredient pricing

### AI and External Services
- Anthropic Claude Sonnet for search planning
- RecipeAPI.io as the primary live recipe provider

### Deployment
- Oracle Cloud Linux VM
- Nginx reverse proxy
- HTTPS
- systemd-managed backend service

## Main Features

- Pantry ingredient entry and normalization
- Live grounded recipe search
- Missing-ingredient detection
- Estimated additional grocery cost
- Time, budget, servings, cuisine, and exclusion preferences
- Best-match and alternative recommendation grouping
- Honest deviation labels such as time-over-target or unknown-price status
- Deterministic recipe ranking
- Protected administration panel
- Built-in and admin-managed ingredient catalog view
- Ingredient alias management
- Manual price management
- Audit logging for administrative changes

## Admin Panel

PantryPilot includes a protected administration interface for maintaining the ingredient and pricing data used by the runtime application.

The effective ingredient catalog combines:

- built-in canonical ingredients, and
- administrator-managed ingredients

without duplicating the built-in taxonomy into a second database structure.

Built-in ingredient identities remain read-only, while their prices can still be maintained through the same pricing system used by the recommendation engine.

## Security Controls

The application includes several production hardening measures:

- salted `scrypt` password hashing
- signed admin sessions
- HttpOnly session cookies
- Secure cookies in production
- SameSite cookie protection
- CSRF protection on administrative mutations
- request-size limits
- rate limiting
- explicit CORS origins
- production API documentation disabled
- minimal public production health response
- configuration validation for production environment values and admin session secrets

## Project Structure

```text
pantrypilot-agent/
├── backend/        FastAPI application, agent logic, repositories and tests
├── frontend/       React/Vite user and admin interfaces
├── docs/           Supporting technical and project documentation
├── AGENTS.md       AI-development workflow guidance
├── CLAUDE.md       Claude Code project guidance
├── TECHNICAL_SPEC.md
├── DECISION_REGISTER.md
└── README.md
```

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a local `.env` from the provided example and configure the required provider keys for live recipe/LLM access.

Run the API:

```bash
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For a production frontend build:

```bash
npm run build
```

## Testing

The project includes focused automated coverage across:

- deterministic domain logic
- agent/orchestrator behavior
- API integration
- admin authentication and CRUD flows
- pricing and ingredient mapping
- frontend recommendation and admin behavior

Typical commands include:

```bash
cd backend
pytest
```

and:

```bash
cd frontend
npm test
```

## Design Principle

> **Use the LLM for reasoning and planning; use deterministic code for facts, constraints, calculations, grounding, and ranking.**

That principle is central to PantryPilot: the AI helps decide *how to search*, while the application code decides *what is safe, valid, grounded, and useful to show the user*.

## Current Status

PantryPilot is an actively developed competition/demo application with a deployed production instance, live recipe-provider integration, an agentic search workflow, deterministic recommendation logic, and an administrative ingredient/pricing interface.
