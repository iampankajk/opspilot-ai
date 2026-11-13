# Task 3 — visitor-owned investigation workspaces

Task 3 implements authenticated incident entry, atomic investigation creation/resume, and durable
workspace retrieval. The owner approved D-023 to stage this work after migration 002, before
relational case/evidence persistence. No case/evidence endpoints, model calls, reviews, numbered
revisions, refresh, or export are included. This records the Task 3 boundary; [Task 4A](CASE_PERSISTENCE.md) now adds migration 003,
atomic backfill, and persisted case listing. Stage-002 results below remain historical.

## Run and inspect

Use the existing [local setup](FOUNDATION_SETUP.md), then explicitly upgrade the local database:

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
```

Current head is `0002_working_workspace`; migration 001 is preserved. Migration 002 adds only
`investigation_states`, `working_drafts`, `thread_states`, and `state_sources`. There are eight
domain tables plus Alembic bookkeeping. The future revision-baseline column/FK remains omitted.
No schema reset, automatic startup migration, or downgrade is required.

Start/restart the usual backend and HTTPS frontend. On [localhost](https://localhost:3000):

1. Start or resume the anonymous demo session.
2. Load `INC-2026-1042` from the incident-reference input.
3. Select **Create or resume investigation**.
4. Inspect the source-backed incident, pinned dataset, investigation/state IDs, and two threads.
5. Use **Reload saved workspace** or reload the browser; the URL retains the public investigation
   UUID and the backend authenticates ownership using the secure cookie.

A newly created visitor clears the prior workspace display/URL and aborts old UI requests.
Protected-request failures never bootstrap a replacement identity automatically. An expired or
lost credential cannot recover an earlier owner's work from a public investigation UUID.

## API boundaries

All three endpoints require the D-019 authenticated visitor. Existing no-store, request-ID,
safe error-envelope, POST Origin/custom-header/JSON, and 4 KiB controls remain in force.

| Request | Behavior |
|---|---|
| `GET /api/v1/incidents/{incident_ref}` | `IncidentEntry`: configured approved catalog's source-backed incident and dataset UUID/label/digest. Unknown valid reference returns 404. |
| `POST /api/v1/investigations` with `{"incident_id":"<UUID>"}` | 201 for a newly committed owned workspace; 200 for an existing fully initialized workspace. No owner, state, dataset, fixture-path, or thread override is accepted. |
| `GET /api/v1/investigations/{investigation_id}/workspace` | `Workspace` for the authenticated owner only. Unknown and foreign IDs return the same 404 code/message/details. |

Workspace responses contain only investigation/state IDs, draft version, pinned dataset,
pinned incident context, and exactly two thread entries. Case counts are **configured fixture
memberships**, labelled accordingly in the UI; they are not persisted case rows or reviewed
outcomes at this stage. The fixture contains one configured case in each thread. No extra
complaints are invented from the scenario's approximate complaint counts.

Workspace retrieval accepts no state selector. Query overrides such as `state_id` are rejected
with 422; passing a state UUID as an investigation UUID returns 404. The current owned draft
is always resolved on the backend. The later case/evidence contracts will add their approved
state/version comparisons when those endpoints exist.

Missing/invalid/expired sessions return the existing 401 conventions before lookup. Missing
incidents return 404. Inconsistent/unavailable fixture content returns 503 `DATASET_UNAVAILABLE`;
initialization failures return 503 `INITIALIZATION_FAILED`; database failures use
`DATABASE_UNAVAILABLE`. Public errors expose no SQL, cookies, credentials, or foreign state.

## Fixture and catalog

`backend/fixtures/synthetic-payments-v0.1.json` transcribes all 14 original source records from
the frozen synthetic evidence package, preserving their original Markdown and table fields.
The two named internal attempts are separate records; each Stripe extract remains one record.
It also holds the approved app-only two-case mapping, two threads, nine source-coverage entries,
three incident-context record references, payload digests, and explicitly declared gaps.

`CURRENT_DATASET_VERSION` selects an exact developer-approved registry entry; its current
explicit code default and example environment value are `synthetic-payments-v0.1`. The loader
checks the whole-file digest, source-package digest, exact source-record inventory, per-record
payload digests, both thread kinds, case references/memberships, and complete record coverage.
There is no version sorting, visitor-supplied path, runtime administration, or fallback version.
Editing the frozen bundle/package requires an explicitly approved version update, not replacing
content under the registered label.

Startup pins and validates this fixture and idempotently registers dataset/incident identities.
An existing version label with a different digest or manifest fails without overwriting it.
Catalog metadata contains record IDs/digests and mappings, not serialized evidence snapshots.
Actual case/evidence payloads remain in the versioned repository fixture until stage 003.
Fixture errors are visible in readiness/catalog access; fix configuration/content and restart
the backend rather than resetting data. Catalog and visitor rows committed earlier survive
a failed investigation initialization.

Each workspace copies its source-backed incident and coverage metadata and pins the dataset
FK. Normal reuse/GETs do not change draft version, refresh evidence, or create numbered history.
Existing workspace reads use the persisted pinned state, including if the current configured
catalog becomes unavailable; they do not substitute another version. New initialization still
fails when its configured dataset is unavailable.

All nine source rows preserve source attribution. Stripe completeness is unverified, bank and
settlement evidence remain not constructed, deployment success/causation are not inferred,
and Support lookup history is attributed to the original synthetic lookup. Missing incident
category/description remain null. Source time retains its original SGT text and second precision,
with UTC normalized bounds; no device-timezone or missing-time guesses are introduced.

## Transaction and concurrency concepts

- One service-owned PostgreSQL transaction inserts the investigation header, state, draft,
  exactly two thread rows, and nine source rows. It validates the assembled response and
  re-authenticates immediately before commit. Any exception rolls back the complete graph.
- The existing unique `(visitor_context_id, incident_id)` constraint resolves competing creates.
  Both callers may initially see no row. One commits; the losing insert rolls back and reads
  the complete committed winner in a fresh transaction. There is no process-local lock.
  See [SQLAlchemy's PostgreSQL conflict handling](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)
  for the idempotent catalog inserts; investigation creation uses the explicit losing-transaction
  rollback path specified in the architecture.
- The draft's **paired FK** `(state_id, investigation_id)` prevents it from pointing at another
  investigation's state. Independent single-column references would not prove the pair belongs
  together. Ownership predicates are still required: foreign keys are not caller authorization.
- Exactly two threads and the complete source set are publication invariants checked inside
  the transaction. PKs and thread-kind checks enforce valid/unique row identities; they cannot
  by themselves count all required children.

## Verification — 13 November 2026

| Check | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q` from `backend/` | 75 backend tests passed, no skips. Includes the foundation/session suite, creation/reuse, independent visitors, safe cross-visitor 404, missing incident, session rejection, stale/foreign state rejection, and composite FK enforcement. |
| Forced concurrent create | Both initial reads were synchronized to miss before either insert; real PostgreSQL returned one 201 and one 200 with the identical complete workspace. The loser performed a fresh winner read. |
| Injected failure after graph insertion | 503; no new investigation/state/draft/thread/source fragments survived. Retry produced one complete workspace. |
| Session expiry during initialization | 401 before commit; the new graph was rolled back. |
| Missing/corrupt/inconsistent fixture and reused label | Rejected visibly, with no fallback or overwrite. |
| App/engine restart and separate real HTTPS process restart | The same cookie and public investigation UUID restored the identical workspace from PostgreSQL. The real-process probe closed its first connection pool, stopped the verification process, then used a new HTTPS client connection after restart. |
| `.venv/bin/alembic current` and `check` | Head `0002_working_workspace`; no new upgrade operations detected. Original migration 001 retained. |
| Offline upgrade SQL review | Eight domain tables plus Alembic metadata; paired draft FK present. Only additive migration 002 was applied to the existing development database. |
| Ruff lint/format, `pip check`, `git diff --check` | Passed; no broken Python requirements. |
| `npm test` | 7 frontend tests passed: prior session tests plus bounded create/read, no identity overrides, no auto-bootstrap on expiry, and malformed workspace rejection. |
| `npm run typecheck`, `npm run build` | Passed after correcting a TypeScript narrowing issue in the response validator. |
| Real HTTPS browser | Incident load, create, both thread buttons, saved-workspace GET, and full page reload passed; investigation/state IDs remained unchanged. Existing user development servers were left running. |

One upstream Starlette warning remains for its legacy httpx TestClient adapter. Most API tests
roll back isolated writes; the real concurrency/restart probes deliberately commit synthetic
test/demo visitors and workspaces to prove durability and leave them for inspection. No user
data or existing database was reset or deleted.

## Changed files and next task

- Backend: `app/catalog.py`, `app/investigations.py`, `app/workspace_schemas.py`; additions to
  `app/models.py`, `app/config.py`, `app/database.py`, `app/main.py`, and `.env.example`.
- Data/schema: `fixtures/synthetic-payments-v0.1.json` and
  `alembic/versions/0002_working_workspace.py`.
- Backend tests: `tests/test_investigations.py`, plus updated API and migration expectations
  in `tests/test_api.py` and `tests/test_postgresql.py`.
- Frontend: `app/investigation-panel.tsx`, `lib/investigations.ts`, `tests/investigations.test.mjs`,
  plus session-context coordination in `app/page.tsx` and `app/visitor-session-panel.tsx`, and
  small styles in `app/globals.css`.
- Documentation: this file, README, Project Status, Decision Log, System Architecture,
  Domain Model, and current local setup instructions. The pre-existing generated
  `frontend/next-env.d.ts` working-tree change is preserved separately.

Work is on `codex/task-3-investigation-workspace`. Nothing was staged, committed, pushed,
merged, or submitted as a PR. Secrets, private environment files, certificates, screenshots,
and temporary verification artifacts remain ignored.

Suggested commit: `feat(investigations): initialize visitor-owned workspaces`

Exact next task, only when requested: stage 003 case/evidence relational persistence and case
listing, with atomic materialization for the existing pinned states and same-state composite
FKs. Evidence-request execution/history must wait for stage 004. Do not create new numbered
revisions or silently refresh/reassign existing workspaces.
