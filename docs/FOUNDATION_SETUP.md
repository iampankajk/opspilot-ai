# Application foundation — local development

This increment verifies **Next.js → same-origin HTTPS API routing → FastAPI → PostgreSQL**.
Task 1 implements only migration boundary 001 from System Architecture §4.5. Task 2 now adds
[anonymous visitor sessions](VISITOR_SESSIONS.md) on that schema. Task 3 adds migration 002,
the validated fixture catalog, and [owned workspace initialization/retrieval](INVESTIGATION_WORKSPACES.md).
Task 4A adds migration 003 and [case/evidence persistence with thread-scoped listing](CASE_PERSISTENCE.md).
Evidence-request execution/history and the remaining investigation journey are deferred.

## Prerequisites and structure

Verified locally with Node 22.21.1, Python 3.12.11, PostgreSQL 18.6, and OpenSSL 3.6.3.
Use a running local PostgreSQL server with permission to create a dedicated role/database.
The helper does not install PostgreSQL, change server authentication, or restart existing services.

```text
backend/
  app/                 Configuration, SQLAlchemy models, readiness API
  alembic/             Explicit, reviewed schema migrations
  tests/               API boundary and real PostgreSQL constraint tests
frontend/
  app/                 Minimal connection-check page
  next.config.ts       Same-origin /api/v1 forwarding
scripts/
  setup-local-db.py     One-time dedicated database setup
  create-dev-cert.sh    Local certificate generation
```

## First-time setup

Run from the repository root. Select Python 3.12 explicitly if `python3` points to an older
system installation. On the current Mac it is `/opt/homebrew/bin/python3.12`.
If your terminal has not loaded nvm, run `. "$HOME/.nvm/nvm.sh"` first. Check `node --version`
shows 22.21.1 in each frontend terminal; an older system Node cannot run this Next.js version.

```sh
nvm use
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -c backend/requirements-dev.lock -e './backend[dev]'
npm --prefix frontend ci
backend/.venv/bin/python scripts/setup-local-db.py
sh scripts/create-dev-cert.sh
```

The database helper creates `opspilot_app` (LOGIN, no superuser/role/database-creation rights),
`opspilot_dev`, and `opspilot_foundation_test`. It generates a random password directly into
ignored `backend/.env` with owner-only permissions, without printing it. Local administrator
authentication uses the usual libpq environment/`.pgpass` configuration. It refuses existing
OpsPilot names or an existing `.env`; it never resets or adopts existing work. Database creation
cannot be one PostgreSQL transaction, so a setup failure can leave a new role/database behind;
inspect that state before retrying, rather than deleting it automatically.

For an existing dedicated database, configure `backend/.env` manually from `.env.example`
instead of running the helper. Keep the `postgresql+psycopg` driver and URL-encode password
characters. Do not paste connection strings into chats or commit them. The existing local
server's authentication policy remains its administrator's responsibility.

The frontend's server-only `BACKEND_ORIGIN` defaults to `http://127.0.0.1:8000`.
An optional ignored `frontend/.env.local` can override it. No frontend database credentials
are needed. Use the one browser origin `https://localhost:3000`, matching backend `PUBLIC_ORIGIN`.

Apply the schema deliberately, from `backend/`:

```sh
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
```

Current expected head: `0003_case_evidence`. Stage 001 creates `visitor_contexts`,
`dataset_versions`, `incidents`, and `investigations`; stage 002 adds `investigation_states`,
`working_drafts`, `thread_states`, and `state_sources`; stage 003 adds `evidence_records`,
`payment_cases`, `case_threads`, `case_evidence_links`, and `evidence_relationships`. There are
13 domain tables plus Alembic's bookkeeping. Schema
migrations import no fixture payloads. Startup validates the explicitly configured
`CURRENT_DATASET_VERSION` (default approved label `synthetic-payments-v0.1`) and registers its
immutable catalog identities idempotently. A missing/mismatched fixture fails visibly.
Application startup never runs `create_all` or migrations. Do not execute a destructive
downgrade against stored work without impact review and explicit approval.

## Run locally

Backend terminal, from `backend/`:

```sh
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend terminal, from the repository root:

```sh
nvm use
npm --prefix frontend run dev
```

Open [the local foundation page](https://localhost:3000). The 30-day development certificate is
self-signed; your browser may require you to handle its local certificate warning. The helper
does not change OS/browser trust settings or overwrite existing certificates. Never disable
TLS verification globally. Next.js's HTTPS mode is for local development; public deployment TLS
is not configured by this task. `npm run start` is an HTTP loopback production-build utility,
not the approved HTTPS browser entry point.

The page should show **Connected** after the browser actually completes the readiness request.
Use **Check again** to issue a fresh request; its request ID should change. Stop only the
processes you started with Ctrl+C when finished. A failed check remains visible and retryable.

## API and security boundary

`GET /api/v1/health` is an operational, read-only readiness endpoint and intentionally requires
no visitor session. It returns no owned data and creates no visitor. Success:

```json
{"status":"ok","database":"connected","schema":"current"}
```

Unreachable PostgreSQL returns 503 `DATABASE_UNAVAILABLE`; a missing/outdated schema returns
503 `SCHEMA_NOT_READY`. Errors use the documented error envelope. Responses include
`X-Request-ID` and `Cache-Control: no-store`; neither credentials nor SQL errors are returned.
The check requires the current migration head, all implemented tables, and the validated
configured catalog. It does not establish case/evidence persistence or full-slice readiness.

The API boundary enforces exact `PUBLIC_ORIGIN`, `X-OpsPilot-Request: 1`, JSON media
type, and the 4 KiB limit for POSTs, including streamed bodies. No cross-origin CORS is enabled.
The product POST routes currently implemented are visitor bootstrap and owned investigation creation/resume. Next.js forwards `/api/v1/*` over loopback; the browser
uses relative URLs over HTTPS. The page's static shell contains no owned data, and readiness
fetches are uncached. No model calls, localStorage identity, default visitor, or owner-ID bypass
exists. D-019's cookie/token authentication is now implemented and tested separately; the
health check remains independent of visitor identity and resource authorization.

## Checks

From `backend/`:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check app alembic tests ../scripts/setup-local-db.py
.venv/bin/ruff format --check app alembic tests ../scripts/setup-local-db.py
.venv/bin/python -m pip check
.venv/bin/alembic upgrade head --sql
```

Tests load `TEST_DATABASE_URL` from ignored `.env`. It must identify a separate dedicated
database whose name ends in `_test`; never point it at a database containing useful work.
Integration tests explicitly upgrade to the current migration head there, roll back their test inserts, and
never drop databases/tables or run downgrades. If unset, PostgreSQL-backed checks are skipped;
that is not evidence of database correctness. API unit tests need no database.

From `frontend/`, after selecting Node 22:

```sh
npm test
npm run typecheck
npm run build
npm audit --audit-level=high
```

From the repository root, with both servers running:

```sh
curl --fail --show-error --cacert .certs/localhost.pem -D - https://localhost:3000/api/v1/health
```

The certificate is explicitly verified here; no insecure curl flag is needed. Expected: HTTP
200, the success JSON, `Cache-Control: no-store`, and an `X-Request-ID`. For a negative browser
check, stop your backend, click **Check again**, observe **Connection unavailable**, restart
the backend, and retry. No reset or new database is needed.

## What to understand

- **Driver vs ORM:** psycopg speaks to PostgreSQL; SQLAlchemy describes tables and manages
  connections. `Mapped[...]` expresses a Python attribute's type; `mapped_column` defines
  its database column. UUID defaults generate application identities, not access credentials.
- **Migration vs model:** ORM metadata describes the intended schema; Alembic records a
  reviewed transition. `op.f(...)` marks an already-named constraint so the naming convention
  is not applied twice. `alembic check` detects schema differences, not semantic correctness.
- **Storage vs authorization:** the unique visitor/incident pair prevents duplicates in storage;
  it cannot establish who the HTTP caller is. Foreign keys restrict deletion and dangling owners.
  The session table's hash-length and timestamp checks protect storage shape, not token issuance.
- **Lifecycle and connection scope:** FastAPI's lifespan creates/disposes the connection pool;
  readiness uses `with engine.connect()` to return each borrowed connection. There is no shared
  ORM Session. The browser session to be added next is a different concept entirely.
- **Readiness and routing:** a live HTTP process can still be unready. The page reports success
  only after API/database/schema checks pass. A rewrite forwards requests without moving the
  browser to a second origin; see the [Next.js rewrite documentation](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites).

D-019 visitor bootstrap/authentication is complete; see its [implementation and verification](VISITOR_SESSIONS.md).
Do not expose investigation creation before the complete working-state initialization exists,
and do not automatically proceed to the next implementation task.

## Verification record — 13 November 2026

| Check (working directory) | Observed result |
|---|---|
| `.venv/bin/alembic upgrade head`, `current`, `check` (`backend/`) | Applied `0001_ownership_catalog`; current head matches; no new upgrade operations detected. |
| `.venv/bin/alembic upgrade head --sql` (`backend/`) | Generated PostgreSQL SQL for four domain tables plus Alembic bookkeeping; reviewed without executing a downgrade. |
| `.venv/bin/python -m pytest -q` (`backend/`) | **25 passed**, no skips; includes eight real PostgreSQL checks. One upstream Starlette warning deprecates its legacy httpx TestClient adapter. |
| `.venv/bin/ruff check app alembic tests ../scripts/setup-local-db.py` and `ruff format --check` (`backend/`) | Passed. |
| `.venv/bin/python -m pip check` (`backend/`) | No broken requirements found. |
| `nvm use`, `npm run typecheck`, `npm run build` (`frontend/`) | Passed using Node 22.21.1. Initial system-Node-16 invocation failed; selecting the documented runtime resolved it. |
| `npm audit --audit-level=high` (`frontend/`) | 0 vulnerabilities reported by npm; this is not a comprehensive security assessment. |
| `sh -n scripts/create-dev-cert.sh`, `git diff --check` (root) | Passed. Credentials, certificates, screenshots, dependencies, and build output confirmed ignored by Git. |
| PostgreSQL catalog inspection | Only four domain tables plus `alembic_version`; all four domain tables empty. Application role is not superuser and cannot create databases/roles. |
| Readiness before migration | Returned `SCHEMA_NOT_READY`; it did not migrate the empty development database. |
| Certificate-verified curl through HTTPS frontend | HTTP 200 with connected/current JSON, `no-store`, and request UUID. |
| POST headers through HTTPS frontend | Missing origin/header returned 403; valid origin/header passed the boundary and returned 405 because health is GET-only. No write endpoint or visitor was created. |
| Browser initial load and **Check again** | Connected; retry produced a new request UUID. The owner handled the development certificate warning. |
| Browser during controlled backend stop/restart | Connection unavailable while stopped; Connected after restart and retry. Development servers left running on 3000/8000. |

Task 1 did not verify session cookies/expiry, visitor authorization, fixture integrity, stages
002–004, or investigation durability. Session checks were subsequently completed in
[Task 2](VISITOR_SESSIONS.md); full investigation authorization remains pending.
No destructive downgrade, deployment, or AI/model call was run.
