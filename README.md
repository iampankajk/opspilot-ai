# OpsPilot AI

A learning-first payment-incident investigation assistant using synthetic evidence.
The approved stack is Next.js/TypeScript, FastAPI/Pydantic, PostgreSQL, SQLAlchemy 2.x,
and Alembic.

## Run the application foundation

Follow [local setup and verification](docs/FOUNDATION_SETUP.md) for dependencies,
dedicated databases, explicit migrations, HTTPS, and development commands.

The application has a connection-check page, `GET /api/v1/health`, and D-019
[anonymous visitor sessions](docs/VISITOR_SESSIONS.md), using migration 001's four
ownership/catalog tables. The full investigation journey, fixture loading, and AI
features are not implemented yet.
See [project status](docs/PROJECT_STATUS.md) and the [approved decisions](docs/DECISION_LOG.md).

## What is included

- `AGENTS.md` — persistent project-wide instructions Codex should read before working.
- `docs/PROJECT_BRIEF.md` — product concept, target workflow, users, scope, and initial technology direction.
- `docs/LEARNING_PLAN.md` — flexible 60-day learning and delivery roadmap.
- `docs/CODEX_WORKFLOW.md` — how to set up the folder and organize focused Codex chats.
- `docs/PROJECT_STATUS.md` — the shared source of truth for current phase, decisions, blockers, and next steps.
- `docs/DECISION_LOG.md` and `docs/decisions/ADR_TEMPLATE.md` — record technical decisions and trade-offs.
- `docs/LEARNING_LOG.md` — daily learning journal.
- `backend/`, `frontend/`, and `scripts/` — application foundation and local setup helpers.

## Learning workflow

Read `AGENTS.md` and the current project documents before starting a bounded task.
The owner writes most implementation code, supported by explanations, hints, review,
and debugging. Follow the approved first-slice contracts rather than implementing
the entire target data model or provisional capabilities from the original brief.
