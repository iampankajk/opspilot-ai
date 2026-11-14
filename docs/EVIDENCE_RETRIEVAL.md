# Task 4B — evidence-request history and bounded case inspection

Implemented on `codex/task-4b-evidence-retrieval`, starting with a verified clean working tree.
Task 4B uses the already approved architecture §4 and domain model §18 contracts. No new
services, dependencies, AI, findings, human review, numbered revisions, refresh, export, or
operational actions were added. Existing migrations 001–003 and the frozen synthetic fixture
remain unchanged. No commit, push, merge, or Task 5 work was performed.

## Migration and API

Run explicitly from `backend/`:

```sh
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
```

Expected head: `0004_evidence_history`. The four additional tables are `evidence_requests`,
`request_sources`, `retrieval_results`, and `retrieval_result_records`: **17 domain tables**
plus Alembic metadata. The migration imports no evidence and does not replace existing data.
Application startup never applies migrations. The downgrade is present for dependency-order
review; it was not run against stored work.

```text
POST /api/v1/investigations/{investigation_id}/threads/{thread_kind}/cases/{case_id}/evidence-requests
```

The body contains `state_id`, `expected_draft_version`, and optionally
`retry_of_request_id`. Extra fields and query parameters are rejected. The existing
4 KiB body limit, JSON content type, exact Origin, and `X-OpsPilot-Request: 1` checks apply.
The server accepts no SQL, arbitrary filters, evidence IDs, source URL, fixture path, or
caller-selected source scope.

The `CaseEvidence` response contains a transport request ID, a distinct persisted evidence
request ID, the committed draft version, all four groups / six requested sources, source
outcomes, original record payloads/provenance/time precision, case association explanations,
and relationships whose endpoints and basis are returned records. Local expansion makes no
further evidence request. An ordinary successful reinspection creates another history entry.

The full request history is durable in PostgreSQL. The UI lists request IDs made during the
current mounted case view; it does not introduce an unapproved history-list/detail endpoint.
Reloading a workspace restores its state/version. Explicit reinspection reads the same stored
evidence and records a new request, rather than pretending to resume earlier execution.

## Transaction, ownership, and deadline boundaries

1. Resolve the cookie credential and lock the owning investigation row. Validate its current
   draft and thread/case membership. Reconcile overdue pending work in an independent commit.
   Compare the expected version and reject a still-running operation or invalid retry reference.
2. Build structured criteria from the pinned manifest: owned state, thread, selected case,
   exactly six sources, explicit manifest record inventory, and a maximum of 14 records.
   Commit one pending request, six expected-source rows, six pending outcomes, and one version
   increment. No authentication, scope, or validation rejection creates request rows.
3. Read each included source through same-state case links, in its own read transaction.
   Queries fetch at most the approved case count plus one: the extra row detects overflow.
   Compare returned identity sets and payload digests against the pinned manifest; omissions
   or extra records become source failures, never silently truncated successful evidence.
   A database failure rolls back before the next source query.
4. Lock and reauthorize the investigation again. Recheck current state, membership, operation
   status, and the version after this operation's own start. Persist source outcomes and exact
   returned memberships together, validate their counts, finish the request, and advance the
   version once more. Commit before returning evidence. A normal request advances version twice.
5. A source failure with other completed sources returns 200 `partial`. All-source failure
   returns 503 with its persisted request ID and committed version. Finalization failure
   rolls back all result changes; a committed pending start remains visible for recovery.
   A late version conflict records only stale history while the original draft is still
   current. A replaced state or expired session receives no result attachment.

Only one pending operation is permitted per investigation, serialized in PostgreSQL rather
than a process-local lock. A manual retry can reference a terminal failed/partial/interrupted
request in the same owned state/thread/case. It creates new request/source/outcome/membership
rows, never changes the prior terminal result, and never duplicates source evidence.

Source execution has a ten-second server budget, checked with a monotonic timer as well as
persisted UTC deadlines. Database pool checkout and connection setup have existing three-second
limits each. A read starts only with room for their six-second reserve; after connection
checkout it sets transaction-local statement/lock timeouts to the lesser of three seconds
and the remaining budget. A deliberately slow PostgreSQL query is cancelled by this timeout.
Finalization uses short transactions and the existing database wait limits. The browser evidence
request timeout is 30 seconds; the installed Next.js proxy also defaults to 30 seconds (verified
in its bundled implementation). Public hosting/proxy timeout configuration is not established.

Workspace/resume/case reads reconcile overdue work under the same owner/current-draft lock.
Overdue sources become interrupted/not-evaluated with null counts, and recovery advances the
version. Recovery commits before a subsequent evidence POST's version rejection; there is no
queue, background retry, or automatic resumption. Replaced/frozen states are not reconciled.

## Evidence fidelity and UI

| Case | Internal | Provider | Logs/traces | Support |
|---|---:|---:|---:|---:|
| Payment failure | 1 | 1 | 2 | 1 |
| Possible duplicate | 2 | 1 | 0 | 3 |

All six source outcomes are present even with zero matches. Evaluated zero matches have
count 0; failed/interrupted or not-evaluated sources have null counts. Availability and
coverage remain separate from query execution. A successfully read provider extract keeps
its unverified completeness. Declared unavailable/not-included/not-constructed sources are
not fabricated as records or treated as query failures.

Original source labels, provider extracts, payloads, source references, synthetic provenance,
and timestamp precision are retained. Lookup-derived candidate orders/attempts keep their
lookup basis. Two attempts, reused idempotency keys, one available provider capture, or a
timeout do not establish duplicate/nonduplicate charges, settlement, or root cause.

The actual React view has persistent source headings, per-section loading feedback, no-match
messages, coverage limitations, errors/retry, native keyboard-operable `details` expansion,
original payloads, and attributed record relationships. Response parsing rejects a different
investigation/state/thread/case, missing sources, invalid counts, duplicate records, and dangling
relationship references. Changing case/state/thread aborts old client work; no automatic POST
or authentication bootstrap occurs on mounting or retry failure. Before an explicit inspection,
the UI loads the current workspace to recover overdue work and use its committed version.

## Verification — 14 November 2026

Executed results:

- `.venv/bin/python -m pytest -q --tb=short` from `backend/`: **155 passed**, no skips,
  one existing upstream warning.
- Frontend `npm test`: **21 passed**; includes response/request contracts and rendering the
  actual React view in loading, error, empty-source, and inspectable-record states.
- Frontend `npm run typecheck`: passed. `npm run build`: passed.
- Ruff lint and format checks across `backend/`: passed. `pip check`: no broken requirements.
- Development/test databases upgraded additively to 004. `alembic current` reports
  `0004_evidence_history`; `alembic check` reports no new operations.
- Real HTTPS process restart: temporary backend stopped/restarted with the dedicated test
  database and a fresh HTTP connection. The original cookie restored the same state/version;
  reinspection preserved evidence content with a distinct new request ID. Temporary processes
  were stopped; existing user servers were not stopped.
- Existing Next.js HTTPS proxy: readiness, fresh visitor cookie forwarding, incident/create,
  both case/evidence mappings, version 0 → 2 → 4, and fresh-connection workspace reload passed.
  This used API calls through the proxy; it was not browser interaction.
- `git diff --check`: passed. Earlier migrations and fixture/package remain unchanged.

The backend suite covers missing/invalid/expired authentication; cross-visitor/state/thread/case
rejection; invalid query criteria; all-source and partial failures; actual failed PostgreSQL
transactions; query timeouts; known source gaps and evaluated zeros; completeness/payload checks;
start/finalization rollback; interruption recovery; stale versions/replaced state; retry history;
composite state/source FKs; concurrent starts; and application/engine/process restart persistence.
The complete migration chain is also checked against an empty, temporary PostgreSQL schema in a
transaction that is rolled back, leaving public data untouched.

Limits: native computer-use access returned **“Computer Use permissions are not granted.”**
No visual browser interaction or screenshot is claimed. Actual React rendering, TypeScript/build,
HTTPS proxy API behavior, and backend process restart were verified separately. A visual check
of both thread views and responsive expansion/retry remains a manual follow-up. The existing
upstream Starlette TestClient deprecation warning remains; no dependency was added to suppress it.
No production, live financial, real customer, or public-deployment behavior is claimed.
The separately recorded local-credential rotation follow-up from Task 4A remains unchanged.

## Changed files and review handoff

- Migration: `backend/alembic/versions/0004_evidence_history_evidence_request_history.py`.
- Backend: new `backend/app/evidence.py` and `evidence_schemas.py`; updated `models.py`,
  `investigations.py`, `main.py`, `api_errors.py`, and `database.py`.
- Backend tests: new `backend/tests/test_evidence.py`; updated `test_investigations.py`
  for shared transaction isolation and `test_postgresql.py` for schema/empty-chain checks.
- Frontend: new `frontend/lib/evidence.ts`, `app/evidence-panel.tsx`, `app/evidence-view.tsx`,
  and `tests/evidence.test.mjs`; updated `lib/investigations.ts`, `app/case-list.tsx`,
  `app/globals.css`, and `tsconfig.json`. Explicit `.ts` imports support the existing Node
  test runner; `allowImportingTsExtensions` is enabled with the existing no-emit configuration.
- Documentation: README, Project Status, Foundation Setup, System Architecture, Domain Model,
  and this verification report. No new architecture approval is implied.

Suggested Conventional Commit:
`feat(evidence): persist bounded retrieval history and case inspection`

Recommended next step: review the diff and perform the remaining visual browser smoke check.
Do not start Task 5 automatically.

Concepts to explain independently: why SQL NULL differs from an evaluated zero; why database
state/source composite FKs complement visitor authentication; why request start and finalization
commit separately; how monotonic budgets and PostgreSQL timeouts complement persisted deadlines;
and why retries append history while source records retain their original identity and meaning.

## Focused P2 QA fixes — 14 November 2026

Only the two reported UX defects were addressed:

- **P2-1:** Relationship anchors now reveal the matching native `details` element within the
  current evidence panel before allowing normal fragment navigation. Other open records remain
  open; native summary collapse/expand and modified-click browser behavior remain available.
- **P2-2:** Each bounded source result is sorted oldest-to-newest using the earliest usable
  normalized source-time bound. `SourceTime` converts known offsets to UTC; original source
  text, timezone, and precision are unchanged. Equal lower bounds use a deterministic record-ID
  tie-break without claiming finer event order. Missing/unusable times follow timestamped
  records. No timestamp, fixture, migration, or evidence membership is created or changed.

Regression checks added: actual component relationship handlers open either target, retain
fragment URLs, preserve native disclosures and existing open records, reopen manually collapsed
records, and leave modified clicks alone; backend API returns the duplicate Zendesk ticket
before its escalation; ordering tests cover different UTC offsets, minute/second/range precision,
equal bounds, missing timezone/time, and preservation of source data.

Executed verification:

- `.venv/bin/python -m pytest -q --tb=short` from `backend/`:
  **157 passed**, no skips, one existing Starlette TestClient deprecation warning.
- `npm test` from `frontend/`: **23 passed**. `npm run typecheck` and `npm run build`: passed.
- Ruff check/format across `backend/`, `pip check`, and `git diff --check`: passed.
- **Chrome P2-1 reproduction passed:** inspected the failure case, left the provider record
  collapsed, opened relationships, and clicked `SYN-STRIPE-FAIL-001`. The native fragment updated
  and provider details became visible. Manual collapse worked; Tab/Enter activation of the
  same relationship reopened the collapsed target. After navigation, Tab reached its summary
  and Space collapsed it again. The selected case and draft version were retained.
- **Chrome P2-2 reproduction passed:** duplicate-case Zendesk records displayed
  `SYN-ZD-TICKET-002` before `SYN-ZD-ESCALATION-001`. Expanding both showed 10:33 SGT then
  10:40 SGT, each with Asia/Singapore timezone and minute precision; both could stay expanded.

Browser access was available for this focused follow-up, superseding the original access
limitation for these two scenarios. This does not claim a complete screen-reader/mobile audit.
The browser created one synthetic visitor/investigation and two evidence requests; existing
investigations and running servers were preserved.

Files changed in this follow-up: `backend/app/evidence.py`, `backend/tests/test_evidence.py`,
`frontend/lib/evidence.ts`, `frontend/app/evidence-view.tsx`, `frontend/tests/evidence.test.mjs`,
and the evidence verification / Project Status notes. Generated Next.js type-file changes were
restored. No commit, push, merge, dependency addition, or subsequent task was performed.
