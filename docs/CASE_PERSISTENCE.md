# Task 4A — case/evidence persistence and thread-scoped listing

Task 4A implements migration stage 003 and the approved `CaseList` endpoint. It adds no
dependencies, evidence-request execution/history, AI, findings, reviews, numbered revisions,
or export. The original fixture JSON and synthetic source package remain unchanged.

## Run and inspect

Use the existing [local setup](FOUNDATION_SETUP.md). Apply the additive schema change explicitly:

```sh
cd backend
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
```

Expected head: `0003_case_evidence`. Migrations 001–002 remain intact. Migration 003 creates
only `evidence_records`, `payment_cases`, `case_threads`, `case_evidence_links`, and
`evidence_relationships`, bringing the implemented schema to 13 domain tables plus Alembic
bookkeeping. It does not load fixture data, reset existing data, or run at application startup.
No destructive downgrade was executed or tested against stored work.

Run backend and frontend separately using the existing commands:

```sh
# Backend terminal, from backend/
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

```sh
# Frontend terminal, from the repository root
. "$HOME/.nvm/nvm.sh"
nvm use
npm --prefix frontend run dev
```

On [localhost](https://localhost:3000), start/resume the demo session, load
`INC-2026-1042`, and create/resume the investigation. Each thread shows one persisted case.
An existing investigation URL also resumes its owned workspace. The public IDs in the URL
are selectors; the Secure/HttpOnly cookie is still the credential.

## Data and transaction boundaries

- A new investigation initializes its original state/draft, two threads, nine coverage rows,
  and the entire case/evidence graph in one transaction. Its initial draft version is 0.
- An older stage-002 investigation is materialized on its first authenticated owned workspace,
  resume, or case-list request. The service locks the investigation row in PostgreSQL and
  uses the dataset pinned to its existing state, never the current catalog as a substitute.
  It retains the owner, investigation/state/draft identities, incident and coverage metadata.
  The committed backfill increments its existing draft version once and updates persistence
  metadata. Later reads/retries do not change it.
- The row lock serializes materialization across processes. Existing unique owner/incident
  handling still resolves competing new creates. A repository may flush dependency boundaries
  but cannot commit independently; any later error or expiry before commit rolls back every
  new graph row and the backfill version change.
- Complete graphs are validated/read from persisted content, independent of the current fixture
  file. An incomplete/inconsistent populated graph fails visibly instead of being overwritten
  or repaired with another dataset. A legacy empty graph requires the approved pinned fixture
  to be available and validated before publication.
- Composite keys/FKs carry `state_id` through case membership, source references, association
  bases, and relationship endpoints. A record existing in another visitor's state cannot
  satisfy a reference in this state. These constraints complement explicit API ownership checks.

The frozen fixture yields exactly:

| Content | Count |
|---|---:|
| Original source records | 14 |
| Application cases / thread memberships | 2 / 2 |
| Case-record associations | 11 |
| Explicit source-field/context relationships | 14 |
| Incident-context records retained outside case membership | 3 |

The failure case contains five records; the possible-duplicate case contains six. The alert,
metric, and deployment timeline remain incident context. Each provider extract stays one
source record. Shared request/idempotency fields are attributed associations; timing is
contextual and does not prove causation, deployment success, deduplication, or duplicate charges.

Original payloads/Markdown, payload digests, source labels, identifier provenance, timestamp
precision, and declared coverage gaps are retained. PostgreSQL JSONB does not preserve object
key order, so projection of field/time arrays is deterministic. Exact `Decimal`/`NUMERIC`
amounts become decimal strings (`48.00`, `120.00`), never JSON floats. The duplicate complaint's
reported order and case-level payment state stay null; the lookup order is separately marked
as a candidate with its basis record. All investigation progress remains `not_started`.

## API and UI

```text
GET /api/v1/investigations/{investigation_id}/threads/{thread_kind}/cases?state_id=<UUID>
```

The route validates the visitor cookie, ownership, selected current draft state, and thread
membership before returning cases. Every case join includes the owned state and requested
thread. It rechecks session validity within the transaction before commit and uses the existing
function-scoped response authentication dependency. No client owner UUID is accepted as proof.

The explicit Pydantic response is the approved `CaseList`/`CaseSummary` contract. Missing,
invalid, and expired credentials retain the existing 401 conventions. Unknown/unowned
investigations return the same safe 404. A foreign/stale state on an owned investigation returns
409 `STALE_STATE`; invalid thread/UUID or missing/extra query fields return 422. No case-detail
or evidence endpoint is added: a case selector override is rejected, not treated as a search.
Errors remain safe, uncached, request-correlated, and visibly retryable where documented.

The UI fetches relative same-origin URLs with cookies and no caching. Thread/state changes
cancel old requests and remount the case view; response scope is checked before display.
It has loading, empty-result, and failure/explicit-retry branches. A stale-state message directs
the visitor to reload the saved workspace. Cases show source-backed reported data, separate
candidate references, payment-context limitations, and primary report identities. No raw session
credential reaches frontend JavaScript.

## Verification — 13 November 2026

| Command/check | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q --tb=short` from `backend/` | **107 passed**, no skips. Includes all 75 previous tests and 32 new persistence/case checks. |
| Migration upgrade on PostgreSQL development/test databases | Applied only additive 003 after 002; prior migrations retained. |
| `.venv/bin/alembic current`, `.venv/bin/alembic check` | Head `0003_case_evidence`; no new upgrade operations detected. Schema inventory is exactly 13 domain tables plus metadata. |
| Legacy initialization/reuse | Cases, workspace retrieval, and resume independently trigger backfill; state/owner/pinned dataset persist, version increments once, repeated requests add no duplicates. |
| Concurrency | Existing forced-race create test passes; concurrent legacy case requests return the same graph at version 1 with no duplicate rows. |
| Source fidelity and boundaries | Exact 14 payloads/raw records/digests and 5/6 case mappings verified. Same incident for two owners remains independent; cross-visitor/stale state/malformed thread/case overrides rejected. |
| Composite FKs | Invalid case/thread/source/record/basis references rejected by PostgreSQL, including a basis record present only in another state. |
| Injected failures and expiry | New initialization and legacy partial inserts roll back completely; legacy version remains unchanged. Session expiry during materialization rejects before commit. Corrupt populated data are rejected without overwrite. |
| Application/engine restart | Identical case list restored with the same visitor cookie and selectors. |
| Separate HTTPS process restart | Temporary backend on port 18000 stopped/restarted; first client pool closed, fresh TLS connection restored identical workspace/cases and source-backed nulls. Cookie remained in memory only. Temporary processes stopped; user servers untouched. |
| `npm test` from `frontend/` on Node 22.21.1 | **11 passed**. Includes selected-state requests, response-scope validation, empty data, nullable reported fields, exact money, and failure/stale retry contracts. |
| `npm run typecheck`, `npm run build` | Passed. Next.js generated type-import changes restored to their pre-task bytes afterward. |
| Ruff check/format, `pip check`, `git diff --check` | Passed; no broken Python requirements. |
| Verified HTTPS readiness through Next.js | Connected/current response after migration 003. |
| Real browser | Observed loading, payment-failure and duplicate case data, candidate-vs-reported order distinction, and full-page restoration with stable investigation/state/version. A real existing stage-002 workspace materialized once to version 1. Screenshot saved in ignored `.local/task4a-cases.jpg`. |

One existing upstream Starlette TestClient deprecation warning remains. Initial integration
runs caught JSONB ordering differences; deterministic projection fixed them before the passing
regression run. Local PostgreSQL checks require the network-enabled execution permission.
No dependency upgrades or database resets were used to resolve the issues.

Verification incident: the initial sandbox-blocked pytest run printed a full setup traceback
containing the private local database password. Subsequent runs used reduced traceback output.
The password is not copied into this report, source, or commits. Treat that local credential as
exposed in the tool transcript and rotate it as a separately authorized local configuration
change; no credential rotation was performed during Task 4A.

Limits: the approved fixed catalog has one case per thread. Empty-result and failure/retry
contracts are covered in frontend unit tests; their UI branches were not forced in the real
browser. A PostgreSQL upgrade and model comparison do not prove public-deployment security.
No live source query, real financial outcome, bank evidence, or full first-slice completion is
claimed. There is no unresolved Task 4A implementation blocker.

## Changed files and review handoff

- Migration: `backend/alembic/versions/0003_case_evidence_case_evidence_graph.py`.
- Backend: `backend/app/models.py`, `database.py`, `investigations.py`, `workspace_schemas.py`,
  and new `fixture_projection.py`/`materialization.py`.
- Backend tests: new `backend/tests/test_cases.py`; updated schema inventory in
  `backend/tests/test_postgresql.py`.
- Frontend: new `frontend/app/case-list.tsx`; updates to `app/investigation-panel.tsx`,
  `app/globals.css`, `lib/investigations.ts`, `tests/investigations.test.mjs`.
- Documentation: README, Project Status, Foundation Setup, System Architecture, Domain Model,
  the historical Task 3 report's forward link, and this report.

Retained `codex/task-3-investigation-workspace` because the owner explicitly prohibited branch
switching. The initial working tree was clean. No staging, commit, push, merge, or PR. Private
environment files, certificates, screenshots, dependencies, and local probes remain ignored.

Suggested Conventional Commit:
`feat(cases): persist evidence and list thread-scoped cases`

Exact next task, only when requested: **Task 4B — stage 004 evidence-request history and bounded
case evidence retrieval/inspection**. Add `evidence_requests`, `request_sources`,
`retrieval_results`, and `retrieval_result_records`; implement the approved case evidence-request
POST and grouped source outcomes with ownership/state/version checks, retry/history, and tests.
Keep AI, findings/reviews, numbered revisions, refresh, and export deferred.

Concepts to explain independently: why same-state composite FKs supplement authentication;
how service-owned transactions and row locks prevent partial/duplicate materialization;
why a draft version changes once for legacy backfill; and why a customer's reported issue,
a lookup candidate, and a verified payment outcome require separate fields and evidence.
