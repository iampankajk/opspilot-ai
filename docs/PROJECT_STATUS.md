# OpsPilot AI — Current Project Status

> Shared status source for all Codex chats. Approved decisions live in [Decision Log](DECISION_LOG.md); explanations live in [Domain Model](DOMAIN_MODEL_ERD_V0.1.md) and [System Architecture](SYSTEM_ARCHITECTURE_V0.1.md).

## Current state

- **Status:** Tasks 1 and 2 (foundation and D-019 anonymous visitor sessions) implemented and locally verified on 13 November 2026. The full approved first slice remains incomplete. Task 3 has not been started.
- **Current phase:** Application foundation implementation, following the finalized first-slice contracts.
- **Current milestone:** Foundation and D-019 bootstrap/reusable authentication complete on migration boundary 001. Await the owner's next bounded task; no investigation creation or further migrations have begun.
- **Target cadence:** Approximately 3 hours per day, flexible 60-day plan; extend for understanding.
- **Implementation started:** Yes. Foundation, visitor-session POST, reusable backend authentication, frontend bootstrap control, and tests exist. No investigation/fixture endpoints are implemented yet. Migration head remains `0001_ownership_catalog`.
- **Approved technical direction:** Next.js; one modular FastAPI/Python backend with Pydantic/OpenAPI; PostgreSQL locally/hosted; SQLAlchemy 2.x; Alembic; anonymous hashed-token secure HttpOnly cookie sessions with expiry; visitor-owned investigations; bounded synchronous execution; configured repository fixtures; full relational snapshots in a later slice. See [Decision Log](DECISION_LOG.md), including D-019–D-022 and the preserved historical review crosswalk.
- **Approved first-slice scope:** Incident entry → visitor-owned investigation → two threads → case listing → inspectable synthetic evidence → durable reload, using the existing 17-table subset. First-slice contracts are in [System Architecture](SYSTEM_ARCHITECTURE_V0.1.md), section 4, and [Domain Model](DOMAIN_MODEL_ERD_V0.1.md), section 18. Only the foundation subset described below is implemented/tested; the full slice is not complete.
- **Still deferred:** The other 12 target tables, AI proposals, human review, revisions/refresh/history/export, annotations, and typed financial analysis; later schema/pointer/immutability details. Hosting/model provider, vector storage, AI orchestration, and general retention/purge remain unselected. No login/account recovery, queue, or microservices are added.

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

## In progress

- Task 2 is complete. Await explicit owner instruction for Task 3; no further implementation proceeds automatically. D-019's session boundary must be retained when investigation endpoints are introduced.
- Remaining first-slice work includes machine-readable fixture transcription/validation, migration stages 002–004, atomic owned initialization, case/evidence/history APIs, and the investigation UI. The future revision-baseline FK remains deferred until history exists.
- The minimal synthetic evidence package remains frozen. Optional tabletop materials remain available; no exercise results or real-world validation have been established.
- All six investigation screens have reviewed first-pass designs. Consolidated UX consistency remains follow-up work, including claim-review-derived progress wording. The approved mandatory correction rationale remains applicable to both threads.

## Remaining UX and evaluation questions

- Consolidate consistency across the existing Overview/Evidence/Findings specifications; do not reopen the approved two-thread workspace structure.
- Refine saved/reopened/read-only revision, whole-dataset refresh, and export interactions for the later slice, preserving individual reviews and review/export timestamp distinctions.
- Finalize repeatable synthetic evaluation materials/reference manifests separately from the optional tabletop. No outcome or real-world value is claimed.
- Resolve remaining case grouping, event identity, finding-version/current-pointer, note carry-forward, and retention details when their dependent features are designed. Not all block the first slice.

## Immediate implementation blockers

No unresolved architecture/product-data blocker is identified for this approved slice. The prior visitor/session, access/migration tooling, and slice-scope decisions are resolved by D-019–D-022. Missing bank evidence, provider completeness, and unresolved root cause are intentional source limitations, not reasons to fabricate data or delay this inspection slice.

Foundation setup is verified with Python 3.12.11, Node 22.21.1, PostgreSQL 18.6, SQLAlchemy 2.0.57, psycopg 3.3.9, Alembic 1.20.1, FastAPI 0.162.5, and Next.js 16.4.6. Same-origin HTTPS readiness and Cookie/Set-Cookie forwarding are verified. The local certificate is self-signed and public deployment TLS is not configured. The test stack emits one upstream Starlette warning about its legacy httpx TestClient adapter; all 50 backend tests and 3 frontend tests pass. Fixture transcription/validation and investigation-level authorization remain pending. Missing or inconsistent fixture content must fail visibly, not be fabricated. Public hosting controls and later retention policy remain outside this task.

## Next actions

1. Review Task 2's [session implementation and verification](VISITOR_SESSIONS.md). Await the owner's explicit next task; Task 3 has not started.
2. Transcribe/validate the frozen 14-record fixture and catalog identities, then implement migration boundary 002, followed by boundaries 003 and 004 in separate increments. Keep exact composite FKs and explicit transaction ownership.
3. Implement atomic owned investigation creation only when its full initialization graph exists, then case/evidence APIs with history and the Next.js investigation journey. Do not implement all 29 target tables or later AI/review/revision capabilities.
4. Run the remaining first-slice acceptance checks against real PostgreSQL and browser cookie behavior; report actual commands/results and update progress from evidence. Task 1's passing checks do not establish session isolation or full-slice completion.

## Recent decisions and historical context


- The project is called OpsPilot AI (working title).
- The plan is approximately 60 days / 180 hours, but it is not a fixed deadline.
- The owner wants AI to focus on explanations, design discussion, hints, reviews, and debugging. AI-written implementation code should remain around 10–20% as a guideline.
- **Fictional-company discovery assumption (not a technical architecture decision):** retain routine GitHub Actions artifacts for 90 days and selected exact production release artifacts for 12 months in a durable but not-yet-selected release/package location; retain deployment ledger metadata for 12 months and Actions logs/runs/checks/statuses for 90 days. Runtime configuration audit retention remains open.
- **Product requirements baseline:** PRD v0.1 remains approved and the problem hypothesis remains unvalidated. Architecture/framework/database choices have since been approved and consolidated in the [Decision Log](DECISION_LOG.md); the approved first-slice contract is now finalized; later capabilities remain deferred.
- **Product-level decisions resolved:** evidence refresh reloads the entire current approved synthetic dataset as a new numbered revision (no live/selective refresh); Markdown export includes optional display name defaulting to “Investigator” without verified-identity implications and separate review/export timestamps shown in Asia/Singapore and ISO 8601 UTC; project owner adjudicates synthetic tests using a per-case reference-evidence manifest, with independent review of disputed results when available. The evaluation manifest is not a tabletop answer key.
- **Fictional exercise-design decision:** use 20 October 2026 and Asia/Singapore (SGT, UTC+08:00) as the tabletop incident reference date/timezone; the 10:30 AM SGT alert maps to `2026-10-20T02:30:00Z`, and its five-minute window is 10:25–10:30 AM SGT (`2026-10-20T02:25Z` to `2026-10-20T02:30Z`, minute precision). Timestamped evidence now exists only in the explicitly synthetic, minimum package at `docs/SYNTHETIC_EVIDENCE_PACKAGE.md`; no source-company records are implied.

- **Current approvals:** [Decision Log](DECISION_LOG.md) preserves D-001–D-018 and adds D-019–D-022 for anonymous visitor sessions, SQLAlchemy 2.x, Alembic, and the initial journey/17-table subset. The finalized contract adds no extra planning document or implementation code.
