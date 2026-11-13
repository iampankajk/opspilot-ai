# OpsPilot AI — Current Project Status

> Shared status source for all Codex chats. Approved decisions live in [Decision Log](DECISION_LOG.md); explanations live in [Domain Model](DOMAIN_MODEL_ERD_V0.1.md) and [System Architecture](SYSTEM_ARCHITECTURE_V0.1.md).

## Current state

- **Status:** Tasks 1–3 and Task 4A (case/evidence persistence and thread-scoped listing) implemented and locally verified on 13 November 2026. The full approved first slice remains incomplete. Task 4B has not started.
- **Current phase:** Application foundation implementation, following the finalized first-slice contracts.
- **Current milestone:** Migration boundary 003, atomic legacy materialization, and authenticated thread-scoped case listing are complete. Await the owner's explicit Task 4B instruction.
- **Target cadence:** Approximately 3 hours per day, flexible 60-day plan; extend for understanding.
- **Implementation started:** Yes. Foundation, session authentication, validated fixture/catalog registration, authenticated incident entry, atomic investigation create/resume, owned workspace retrieval, and a minimal frontend flow exist. Migration head is `0003_case_evidence`; 13 domain tables are implemented.
- **Approved technical direction:** Next.js; one modular FastAPI/Python backend with Pydantic/OpenAPI; PostgreSQL locally/hosted; SQLAlchemy 2.x; Alembic; anonymous hashed-token secure HttpOnly cookie sessions with expiry; visitor-owned investigations; bounded synchronous execution; configured repository fixtures; full relational snapshots in a later slice. See [Decision Log](DECISION_LOG.md), including D-019–D-022 and the preserved historical review crosswalk.
- **Approved first-slice scope:** Incident entry → visitor-owned investigation → two threads → case listing → inspectable synthetic evidence → durable reload, using the existing 17-table subset. First-slice contracts are in [System Architecture](SYSTEM_ARCHITECTURE_V0.1.md), section 4, and [Domain Model](DOMAIN_MODEL_ERD_V0.1.md), section 18. The implementation reaches persisted case listing; evidence-request execution/history is still pending.
- **Still deferred:** The remaining four first-slice history tables, AI proposals, human review, revisions/refresh/history/export, annotations, and typed financial analysis; later schema/pointer/immutability details. Hosting/model provider, vector storage, AI orchestration, and general retention/purge remain unselected. No login/account recovery, queue, or microservices are added.

## Completed

- Agreed on the OpsPilot AI project direction.
- Agreed to use a learning-first, full software development lifecycle.
- Agreed to prioritize independent implementation and deep understanding over generated code.
- Prepared initial Codex project documentation.
- Mapped the assumed current-state APAC payment incident workflow, evidence sources, roles, approvals, recovery, financial remediation, post-incident review, and knowledge maintenance in `docs/CURRENT_STATE_WORKFLOW.md`.
- Agreed and recorded refund execution case closure criteria, including reconciliation, audit completeness, customer notification, exception clearance, separately tracked bank-posting follow-up, and Finance / Payments Remediation Owner review.
- Recorded proposed fictional-company deployment evidence retention: 12-month deployment ledger metadata and selected production release artifacts, with 90-day workflow logs and routine CI artifacts; storage implementation and actual retention/access behavior remain unvalidated.
- PRD v0.1 formally approved as the product requirements baseline. The original problem hypothesis remains unvalidated.
- UX Blueprint v0.1 approved by the product owner in `docs/UX_BLUEPRINT_V0.1.md`.
- Payment Failures Overview screen first-pass design completed and reviewed in `docs/PAYMENT_FAILURES_OVERVIEW_SCREEN_V0.1.md`.
- Payment Failures Evidence screen first-pass design completed, reviewed, and approved by the product owner in `docs/PAYMENT_FAILURES_EVIDENCE_SCREEN_V0.1.md`.
- Payment Failures Findings screen first-pass design completed and reviewed in `docs/PAYMENT_FAILURES_FINDINGS_SCREEN_V0.1.md`.
- Possible Duplicates Overview screen first-pass design completed and reviewed in `docs/POSSIBLE_DUPLICATES_OVERVIEW_SCREEN_V0.1.md`.
- Possible Duplicates Evidence screen first-pass design completed and reviewed in `docs/POSSIBLE_DUPLICATES_EVIDENCE_SCREEN_V0.1.md`.
- Possible Duplicates Findings screen first-pass design completed and reviewed in `docs/POSSIBLE_DUPLICATES_FINDINGS_SCREEN_V0.1.md`.

- Discussed and documented the conceptual/logical model, including two ERDs, a 29-table target proposal, composite keys/citations, visitor ownership, and draft/revision persistence in [Domain Model](DOMAIN_MODEL_ERD_V0.1.md). This is design evidence, not an implemented schema.
- Owner approved the thirteen review decisions; consolidated them into existing canonical D-004/D-005 and new D-008–D-018, without renumbering D-001–D-007.
- Compared modular monolith/microservices, frontend/backend boundaries, FastAPI/Flask, PostgreSQL/SQLite, and snapshot alternatives. Approved choices and unapproved alternatives remain distinct.
- Prepared the component/API/first-slice design in [System Architecture](SYSTEM_ARCHITECTURE_V0.1.md); journey and 17-table scope were subsequently approved in D-022. Foundation implementation has now begun; the full journey remains pending.
- Reorganized design documentation into domain/persistence and system/application responsibilities, with cross-links and a central approval register.

- Recorded owner approvals D-019 (anonymous sessions), D-020 (SQLAlchemy 2.x), D-021 (Alembic), and D-022 (first-slice journey/subset), preserving all earlier decision IDs.
- Finalized token lifecycle/security, six HTTP endpoints with request/response/error contracts, two explicit case mappings over 14 existing source records, four schema migration boundaries, and a first-slice acceptance checklist. Session fields fit on `visitor_contexts`; no extra domain table was added.

- Implemented Task 1 foundation: Next.js/TypeScript connection page; FastAPI/Pydantic operational readiness endpoint; synchronous SQLAlchemy/psycopg connectivity; Alembic configuration and only migration `0001_ownership_catalog` (`visitor_contexts`, `dataset_versions`, `incidents`, `investigations`). No fixture payloads or later tables were added.
- Created dedicated local development/test databases and a restricted application role; private generated credentials and local certificate/key are ignored. Added [local setup, checks, and concept explanations](FOUNDATION_SETUP.md).
- Verified migration upgrade/current/schema comparison, 25 API/PostgreSQL tests, Python lint/format/dependency checks, TypeScript checking, and Next.js production build. HTTPS API readiness returned 200 with `no-store` and a request ID. Browser showed Connected, a fresh ID on retry, Connection unavailable during controlled backend downtime, and Connected after restart. The owner handled the local certificate warning. At Task 1 completion, session behavior and the remaining first-slice acceptance checklist were still pending; Task 2 results follow below.

- Task 2 subsequently implemented D-019 `POST /api/v1/visitor-session`: 256-bit random tokens, only SHA-256 digests persisted, Secure/HttpOnly/SameSite=Lax/Path=/ host cookies without Domain, configurable 86400-second absolute expiry, stable UTC serialization, reuse without extension, explicit fresh bootstrap, and safe rejection/clearing of invalid/expired credentials. No new schema revision or dependency was needed.
- Added `CurrentVisitor`, a reusable function-scoped authentication dependency that resolves the cookie on entry and rechecks before protected data is sent. Visitor IDs in request bodies/headers/query strings are never credentials. Future write services still need session/owner/state checks within their commit transactions.
- Verified **50 backend tests**, **3 frontend tests**, TypeScript and build, lint/format/dependency checks, and unchanged Alembic head/schema. **14 real-browser checks** passed through the HTTPS proxy against an explicitly launched test-only backend: cookie acceptance/forwarding and JavaScript inaccessibility, reuse, invalid-token/expired-cookie clearing, invalidation, expiry, and UUID impersonation rejection. Expiry used a test-only virtual clock. Independent cookie jars are covered by backend tests; full investigation authorization is not implemented or claimed.
- Restored the normal backend after testing; test probe/control routes are absent from `app.main:app`. Verified creation and reuse on the real application page. Details and repeatable commands are in [Visitor Sessions](VISITOR_SESSIONS.md). One upstream Starlette TestClient deprecation warning remains; no checks were skipped.

- Task 3: inspected `main`, its working tree, and PostgreSQL head 001; created `codex/task-3-investigation-workspace`. Preserved the pre-existing generated `frontend/next-env.d.ts` change. No staging, commit, push, merge, or PR was performed.
- Recorded explicit owner approval D-023 for stage-002 workspace publication. Atomically initialize the owned investigation, pinned state, draft, exactly two threads, and nine truthful coverage rows; case counts come from the pinned validated fixture and are labelled configured cases. Case/evidence persistence is deferred.
- Added the reviewed `synthetic-payments-v0.1` repository fixture with all 14 original records, source/payload/whole-file digest validation, exact mappings, declared gaps, and idempotent immutable catalog registration. Missing/corrupt/inconsistent content fails visibly without fallback or overwrite.
- Implemented authenticated `GET /api/v1/incidents/{incident_ref}`, `POST /api/v1/investigations` (201 new / 200 existing), and owned `GET /api/v1/investigations/{id}/workspace`. Existing PostgreSQL owner/incident uniqueness handles true concurrent creates through losing-transaction rollback and a fresh complete-winner read. Unknown and foreign workspaces share a safe 404; unsupported state/owner/fixture overrides cannot target another workspace.
- Applied only additive migration `0002_working_workspace`, retaining migration 001 and all existing sessions/data. It creates `investigation_states`, `working_drafts`, `thread_states`, and `state_sources`, including the paired draft/state investigation FK. Initialization failure or expiry before commit rolls back all new graph rows. No numbered revisions or later tables were added.
- Verified **75 backend tests**, **7 frontend tests**, TypeScript/build, Ruff lint/format, dependency checks, and Alembic head/schema consistency. Forced-race concurrency, graph rollback, cross-visitor isolation, missing/expired/invalid credentials, bad fixtures, and application/engine restart checks passed. A separate real HTTPS process restart with a fresh client connection restored the identical workspace and cookie authentication.
- Real browser: incident load, create, both thread controls, explicit workspace retrieval, and full page reload passed with stable investigation/state IDs. Existing user development servers were not stopped. Temporary verification processes were stopped afterward. [Workspace implementation and verification](INVESTIGATION_WORKSPACES.md) records exact commands, changed files, limits, and the next task.

- Task 4A: retained the clean `codex/task-3-investigation-workspace` branch at the owner's instruction; no branch switch, staging, commit, push, merge, or PR. Applied additive migration `0003_case_evidence` after 002 in development and test databases; existing history/data were retained.
- Added the five approved graph tables with same-state composite FKs. Materialize exactly 14 source records, two cases, two memberships, 11 case-record links, and 14 explicitly attributed relationships. Original fixture/package and their digests are unchanged; no attempts/events or later workflow tables were introduced.
- New initialization is atomic at draft version 0. Owned legacy access serializes on its investigation row and atomically loads that state's pinned dataset; owner/state/draft are preserved and the draft version advances once. Complete graphs are read from PostgreSQL; incomplete/inconsistent graphs fail visibly without overwrite.
- Added authenticated/current-state `GET /api/v1/investigations/{id}/threads/{thread}/cases?state_id=...` with safe foreign/unknown 404, stale-state 409, and invalid/extra input 422. UI displays each thread's persisted case with loading, failure/retry, and empty-result branches. Reported orders/money remain separate from lookup candidates; unknown payment outcomes and coverage gaps stay explicit.
- Verified **107 backend tests**, **11 frontend tests**, TypeScript and production build, Ruff lint/format, Python dependency consistency, Alembic current/check, and HTTPS readiness. Backend checks include real PostgreSQL concurrency, legacy/new rollback, expiry before commit, exact fixture mapping, composite FK rejection, ownership isolation, and app/engine restart. A separate real HTTPS process restart restored identical workspace/case data using a fresh connection and the original in-memory cookie.
- Browser verification observed loading and both mapped case lists, candidate-vs-reported order semantics, and identical workspace/state/version after full reload. This browser resumed a real stage-002 workspace and materialized it once to version 1. Empty-list data and failure/retry contracts are tested in frontend unit tests; their UI branches were not forced against the fixed nonempty catalog. Existing development servers remain running; temporary restart-probe processes were stopped. See [Task 4A implementation and verification](CASE_PERSISTENCE.md).

## In progress

- Task 4A is complete. Await explicit owner instruction for Task 4B; no further implementation proceeds automatically. Retain D-019 authentication and pinned state ownership.
- Remaining first-slice work is stage 004 evidence-request history/execution. Legacy stage-002 materialization is now implemented. The future revision-baseline FK remains deferred until numbered history exists.
- The minimal synthetic evidence package remains frozen. Optional tabletop materials remain available; no exercise results or real-world validation have been established.
- All six investigation screens have reviewed first-pass designs. Consolidated UX consistency remains follow-up work, including claim-review-derived progress wording. The approved mandatory correction rationale remains applicable to both threads.

## Remaining UX and evaluation questions

- Consolidate consistency across the existing Overview/Evidence/Findings specifications; do not reopen the approved two-thread workspace structure.
- Refine saved/reopened/read-only revision, whole-dataset refresh, and export interactions for the later slice, preserving individual reviews and review/export timestamp distinctions.
- Finalize repeatable synthetic evaluation materials/reference manifests separately from the optional tabletop. No outcome or real-world value is claimed.
- Resolve remaining case grouping, event identity, finding-version/current-pointer, note carry-forward, and retention details when their dependent features are designed. Not all block the first slice.

## Immediate implementation blockers

Verification follow-up: an initial sandbox-blocked pytest traceback exposed the local database password in tool output. Credentials were not changed or committed. Rotate that credential in a separately authorized configuration task; see [Task 4A verification notes](CASE_PERSISTENCE.md).

No unresolved architecture/product-data blocker is identified for this approved slice. The prior visitor/session, access/migration tooling, and slice-scope decisions are resolved by D-019–D-022. Missing bank evidence, provider completeness, and unresolved root cause are intentional source limitations, not reasons to fabricate data or delay this inspection slice.

Foundation setup is verified with Python 3.12.11, Node 22.21.1, PostgreSQL 18.6, SQLAlchemy 2.0.57, psycopg 3.3.9, Alembic 1.20.1, FastAPI 0.162.5, and Next.js 16.4.6. Same-origin HTTPS readiness, Cookie/Set-Cookie forwarding, and owned workspace access are verified. The local certificate is self-signed and public deployment TLS is not configured. One upstream Starlette TestClient deprecation warning remains; all 107 backend tests and 11 frontend tests pass. Relational case/evidence materialization and owned thread listing are implemented; evidence-request execution/history and its descendant authorization remain pending. D-023 resolves the staged-initialization conflict identified at Task 3 start. No unresolved Task 4A blocker remains. Public hosting controls and later retention policy remain outside this task.

## Next actions

1. Review the [Task 4A implementation and verification](CASE_PERSISTENCE.md) and uncommitted changes. Suggested commit: `feat(cases): persist evidence and list thread-scoped cases`.
2. Only when explicitly requested, Task 4B: add stage 004 (`evidence_requests`, `request_sources`, `retrieval_results`, `retrieval_result_records`), then implement the approved bounded case evidence-request endpoint and inspection UI with source outcomes, retry/history, and state/version/ownership checks.
3. Complete remaining first-slice acceptance checks. Do not introduce AI/reviews/revisions/export or silently refresh existing states.

## Recent decisions and historical context


- The project is called OpsPilot AI (working title).
- The plan is approximately 60 days / 180 hours, but it is not a fixed deadline.
- The owner wants AI to focus on explanations, design discussion, hints, reviews, and debugging. AI-written implementation code should remain around 10–20% as a guideline.
- **Fictional-company discovery assumption (not a technical architecture decision):** retain routine GitHub Actions artifacts for 90 days and selected exact production release artifacts for 12 months in a durable but not-yet-selected release/package location; retain deployment ledger metadata for 12 months and Actions logs/runs/checks/statuses for 90 days. Runtime configuration audit retention remains open.
- **Product requirements baseline:** PRD v0.1 remains approved and the problem hypothesis remains unvalidated. Architecture/framework/database choices have since been approved and consolidated in the [Decision Log](DECISION_LOG.md); the approved first-slice contract is now finalized; later capabilities remain deferred.
- **Product-level decisions resolved:** evidence refresh reloads the entire current approved synthetic dataset as a new numbered revision (no live/selective refresh); Markdown export includes optional display name defaulting to “Investigator” without verified-identity implications and separate review/export timestamps shown in Asia/Singapore and ISO 8601 UTC; project owner adjudicates synthetic tests using a per-case reference-evidence manifest, with independent review of disputed results when available. The evaluation manifest is not a tabletop answer key.
- **Fictional exercise-design decision:** use 20 October 2026 and Asia/Singapore (SGT, UTC+08:00) as the tabletop incident reference date/timezone; the 10:30 AM SGT alert maps to `2026-10-20T02:30:00Z`, and its five-minute window is 10:25–10:30 AM SGT (`2026-10-20T02:25Z` to `2026-10-20T02:30Z`, minute precision). Timestamped evidence now exists only in the explicitly synthetic, minimum package at `docs/SYNTHETIC_EVIDENCE_PACKAGE.md`; no source-company records are implied.

- **Current approvals:** [Decision Log](DECISION_LOG.md) preserves D-001–D-022 and adds D-023 for the explicitly approved Task 3 staged workspace. The overall 17-table first-slice boundary and deferred capabilities are unchanged.
