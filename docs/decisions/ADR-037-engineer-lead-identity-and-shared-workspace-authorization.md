# ADR-037: Engineer/Lead Identity and Shared Workspace Authorization (D-037)

- **Status:** Accepted
- **Date:** 2026-11-27
- **Decision owner:** Project owner
- **Related decisions:** D-014, D-018, D-019, D-020, D-021, D-036 (preserved); [Human Findings Review MVP PRD](../OpsPilot_AI_Human_Findings_Review_MVP_PRD.md) (Decisions 1, 8, 28–30; FR-11, FR-12); [Design Handoff](../HUMAN_FINDINGS_REVIEW_DESIGN_HANDOFF.md)

---

## Context

Under **D-018** and **D-019**, OpsPilot AI authenticates each caller through a single anonymous cookie (`__Host-opspilot_visitor`, or `opspilot_visitor` on opt-in local HTTP) mapped to one `visitor_contexts` row. That single `visitor_context_id` currently serves two roles simultaneously:

1. **Workspace / tenant isolation boundary:** `investigations` enforces `UNIQUE (visitor_context_id, incident_id)`, and every query filters by `Investigation.visitor_context_id == current_visitor.visitor_context_id`, returning `404 NOT_FOUND` for unknown or foreign IDs.
2. **Caller identity:** Every action in the investigation is attributed implicitly to that single anonymous cookie, with no concept of actor identity or role.

The approved **Human Findings Review MVP PRD** introduces a strict two-stage governance workflow on a **shared investigation** (PRD Decisions 1, 8, 28–30; FR-11, FR-12):

- **Payments Operations Engineer (`engineer`)** inspects evidence, triggers explicit AI generation/follow-ups, validates findings, rejects unsupported claims, requests further investigation, proposes human-corrected revisions, validates their own proposed corrections, and recommends impact adjustments.
- **Payments Lead / Incident Commander (`lead`)** views a queue of validated current revisions, confirms or overrides impact classification, and approves, returns for correction, or permanently rejects findings.
- **Separation & isolation invariants:**
  - Both roles must securely view and act on the **same investigation** without breaking cross-workspace isolation between independent visitors/demo workspaces.
  - Actor identity and role must be **server-verified**; client-supplied role headers, body fields, or UUID claims must never be trusted.
  - Engineers cannot self-approve findings, and Lead credentials/sessions must not be forgeable or escalatable from an Engineer session.
  - Existing D-019 visitor-session contracts (479 backend tests, local HTTPS, and opt-in `ALLOW_INSECURE_LOCAL_HTTP` development support) must remain compatible.

---

## Options considered

1. **Option A — Client-selected role header or in-session role switcher on the single `visitor_contexts` cookie (Rejected)**
   - *Design:* Keep one `visitor_contexts` cookie per workspace and let the browser send `X-Actor-Role: lead` or call `POST /auth/switch-role {"role": "lead"}` using the Engineer cookie.
   - *Drawbacks:* Fails PRD Decision 30 and FR-11. Trusts client intent or lets an authenticated Engineer escalate their own session into Lead in one request, enabling trivial privilege escalation and self-approval.

2. **Option B — Full username/password accounts, email verification, or external OIDC/OAuth (Rejected for MVP)**
   - *Design:* Add user registration, password hashing (`argon2`/`bcrypt`), login/recovery flows, workspace invite emails, or an external identity provider.
   - *Drawbacks:* Violates D-019 ("No login or account recovery in the MVP") and project simplicity rules (`AGENTS.md`), introduces credential-management dependencies and PII/recovery scope, and blocks Frictionless local/hosted synthetic-data evaluation.

3. **Option C — Shared workspace (`visitor_contexts`) + server-provisioned fictional actors (`workspace_actors`) + independent server-verified sessions (`actor_sessions`) (Recommended)**
   - *Design:* Retain `visitor_contexts` as the **workspace/tenant scope** so `investigations.visitor_context_id` and `UQ (visitor_context_id, incident_id)` remain intact. Separate **actor identity and role** into `workspace_actors` (`engineer` and `lead` fictional personas scoped to a workspace) and **session credentials** into `actor_sessions` (opaque 256-bit random tokens, SHA-256 hashed, `HttpOnly` cookie). At shared workspace creation (`POST /api/v1/auth/workspaces`), the server provisions both fictional actors and emits one-time server-generated 256-bit access codes (stored only as SHA-256 digests) so an independent Lead browser/client can authenticate to the same workspace via `POST /api/v1/auth/login` without exposing Lead access to an Engineer session or leaking workspace membership by UUID.
   - *Trade-offs:* Adds two small relational tables (`workspace_actors`, `actor_sessions`) and four `/api/v1/auth/*` endpoints while avoiding passwords, email, PII, OAuth, or breaking D-019 tests. One-time Lead access codes cannot be recovered if lost (matching D-019's no-recovery model).

---

## Decision

Adopt **Option C**: decouple **workspace ownership** (`visitor_contexts`) from **actor identity/role** (`workspace_actors`) and **session credentials** (`actor_sessions`), using a minimal, server-verified fictional actor identity system.

### 1. Engineer and Lead Actor Identities & Role Assignment

- Each workspace (`visitor_contexts` row) owns workspace-scoped fictional actors in `workspace_actors`:
  - **`ops-engineer-1`**: `display_name = "Maya Lin"`, `role = "engineer"`
  - **`payments-lead-1`**: `display_name = "Devon Patel"`, `role = "lead"`
- **Schema supports multiple actors per workspace** (`CHECK (role IN ('engineer', 'lead'))`, `UNIQUE (visitor_context_id, actor_ref)`) so automated tests and future increments can add a second Engineer or Lead within the same workspace without schema changes.
- **Server-only role assignment:** `role` is assigned exclusively by the server when provisioning `workspace_actors`. It is immutable for the lifetime of the actor and session. Client-supplied roles in headers (`X-Actor-Role`, etc.), query parameters, or request bodies are ignored or rejected (`422 VALIDATION_ERROR` via `ConfigDict(extra="forbid")`).

### 2. Shared Investigation Access Across Both Roles

- `investigations` continues to reference `visitor_contexts.visitor_context_id` with `UNIQUE (visitor_context_id, incident_id)`.
- Every `actor_sessions` row has a composite foreign key `(visitor_context_id, actor_id)` referencing `workspace_actors(visitor_context_id, actor_id)`.
- When **Maya Lin (`engineer`)** creates an investigation in Workspace `W1`, `Investigation.visitor_context_id` is `W1`.
- When **Devon Patel (`lead`)** authenticates to `W1` via `POST /api/v1/auth/login` in an independent browser/cookie jar, his `ActorSession` resolves `visitor_context_id = W1`, `actor_id = devon_id`, `role = 'lead'`.
- Both actors pass the `Investigation.visitor_context_id == current_actor.visitor_context_id` ownership check for that same `investigation_id`, while audit trails and revision attribution record each caller's distinct `actor_id` and `role`.
- A read-only `GET /api/v1/investigations` endpoint (scoped strictly to `current_actor.visitor_context_id`) allows an independent Lead to discover existing investigations in their shared workspace without needing to copy an `investigation_id` URL parameter manually.

### 3. Preserving Cross-Workspace Isolation

- Workspace `W1` and Workspace `W2` remain completely isolated:
  - `actor_sessions` cannot span workspaces (enforced by composite FK `(visitor_context_id, actor_id)`).
  - Every investigation and descendant query filters by `Investigation.visitor_context_id == current_actor.visitor_context_id` inside the transaction.
  - Knowing a foreign `investigation_id` or `visitor_context_id` UUID grants zero access:
    - Cross-workspace investigation reads or writes return `404 NOT_FOUND` (identical to an unknown UUID).
    - `POST /api/v1/auth/login` with an unknown `visitor_context_id`, wrong `actor_ref`, or wrong `access_code` returns a uniform `401 AUTHENTICATION_FAILED` so valid workspace UUIDs cannot be enumerated.

### 4. Session & Authorization Boundaries (`401` / `403` / `404` Precedence)

Every protected endpoint evaluates checks in a fixed, fail-closed order:

1. **Transport / CSRF middleware (`POST` routes):** Existing `api_boundary` checks `Origin == PUBLIC_ORIGIN` and `X-OpsPilot-Request == "1"` (`403 REQUEST_ORIGIN_FORBIDDEN`), `Content-Type: application/json` (`415`), and body cap (`413`). All state-changing auth and review endpoints use `POST`.
2. **Authentication (`401`):** `CurrentActor` (`scope="function"`) hashes the cookie token (`SHA-256`) and joins `actor_sessions`, `workspace_actors`, and `visitor_contexts`:
   - Missing cookie → `401 SESSION_REQUIRED`
   - Malformed token, unknown digest, `actor_sessions.invalidated_at IS NOT NULL`, `workspace_actors.disabled_at IS NOT NULL`, or `visitor_contexts.invalidated_at IS NOT NULL` → `401 SESSION_INVALID` (`clear_cookie=True`)
   - `actor_sessions.expires_at <= clock()` or `visitor_contexts.expires_at <= clock()` → `401 SESSION_EXPIRED` (`clear_cookie=True`)
   - Re-authenticated before protected responses leave FastAPI and again inside write transactions after `SELECT ... FOR UPDATE`.
3. **Input validation (`422`):** Strict Pydantic schemas (`extra="forbid"`) reject malformed UUIDs, unknown fields, or invalid query overrides.
4. **Workspace & resource ownership (`404`):** Lookup `Investigation` filtered by `(investigation_id, visitor_context_id == current_actor.visitor_context_id)` (plus `state_id` / `thread_kind` / `case_id` scoping). If missing or belonging to another workspace → **`404 NOT_FOUND`**.
   - *Critical ordering rule:* Workspace ownership (`404`) is checked **before** role authorization (`403`) on investigation-scoped routes so a cross-workspace probe never leaks whether a foreign `investigation_id` exists.
5. **Role authorization (`403`):** Checked against server-derived `current_actor.role` inside the same transaction → **`403 ROLE_FORBIDDEN`** when the caller's role is not permitted for the action.
6. **Concurrency & domain invariants (`409` / `403` / `422`):** Stale `state_id` / `draft_version` / `revision_id` returns `409`; self-approval returns `403 SELF_APPROVAL_FORBIDDEN`.

#### Endpoint Authorization Matrix (Tasks 6A–6E)

| Action / Endpoint | Unauth | Foreign Workspace (`W2`) | Same-Workspace Engineer | Same-Workspace Lead |
|---|---|---|---|---|
| `POST /auth/workspaces`, `POST /auth/login`, `POST /visitor-session` | Allowed (entry) | N/A (new workspace or credentialed login) | Allowed (`/auth/workspaces` creates a separate new empty workspace only; never accesses or mints credentials for an existing workspace) | Allowed |
| `GET /auth/session`, `POST /auth/logout` | `401` | N/A (scoped to caller's cookie) | Allowed | Allowed |
| `GET /incidents/{ref}`, `GET /investigations` | `401` | N/A (catalog or caller's own workspace list) | Allowed | Allowed |
| `POST /investigations` (create/resume) | `401` | N/A (creates/resumes in caller's own workspace) | Allowed | `403` |
| `GET /investigations/{id}/workspace`, `GET .../cases`, `POST .../evidence-requests`, `GET .../findings`, `GET .../audit-events` | `401` | `404` | Allowed | Allowed |
| `POST .../finding-generations`, `POST .../finding-followups` | `401` | `404` | Allowed | `403` |
| Engineer review actions (`validate`, `request_further_investigation`, `reject_validation`, `propose_correction`, `recommend_impact`) | `401` | `404` | Allowed | `403` |
| Lead Queue (`GET .../lead-queue`) & Lead actions (`approve`, `return_for_correction`, `permanently_reject`, `confirm/override` impact, `bulk-approve`) | `401` | `404` | `403` | Allowed (+ self-approval guard) |

*Note on `POST .../evidence-requests`:* Both `engineer` and `lead` may inspect evidence against the pinned state because the UI has no separate `GET .../evidence` endpoint today and PRD Journey A requires the Lead to independently inspect evidence. Neither role can modify evidence records.

### 5. Separation of Engineer Validation and Lead Approval

- **Stage 1 (`engineer` only):** Only an authenticated `engineer` may generate AI findings, propose human corrections, validate evidence, reject validation, request further investigation, or recommend impact adjustments. Same-engineer validation of their own human correction is explicitly permitted (PRD Decision 8).
- **Stage 2 (`lead` only):** Only an authenticated `lead` may query the Lead Queue (`awaiting_lead_review` non-superseded current revisions) or execute `approve`, `return_for_correction`, `permanently_reject`, `confirm/override` impact, or `bulk-approve`.
- **Database audit integrity (Task 6B readiness):** `workspace_actors` includes `UNIQUE (actor_id, role)` so Task 6B's `finding_review_events` table can enforce a composite FK `(actor_id, actor_role) REFERENCES workspace_actors(actor_id, role)`, guaranteeing at the database level that an audit event cannot record a mismatched role for an actor.

### 6. Protection Against Impersonation, Privilege Escalation, and Self-Approval

1. **No impersonation via public IDs or headers:**
   - `visitor_context_id`, `actor_id`, and `actor_ref` are public identifiers, never credentials.
   - Authenticating to an existing workspace via `POST /api/v1/auth/login` requires a server-issued 256-bit CSPRNG `access_code` (`secrets.token_urlsafe(32)`, 43-char base64url) whose SHA-256 digest matches `workspace_actors.access_code_hash` for `(visitor_context_id, actor_ref)`.
   - Raw session tokens and `access_code` values are emitted **only** at initial provisioning (`POST /api/v1/auth/workspaces`, `201`, `Cache-Control: no-store`) and are never stored in plaintext, never returned by ordinary APIs (`GET /api/v1/auth/session`, `GET /api/v1/investigations`, domain routes, or error `details`), and never recorded in application, validation, or SQL logs.
2. **No privilege escalation:**
   - There is no role-switch or upgrade endpoint that mutates `actor_sessions.actor_id` or `workspace_actors.role`.
   - `POST /api/v1/auth/workspaces` returns one-time `access_code`s **only once** at brand-new empty-workspace creation (`W_new`). An Engineer session on any existing workspace (`W1`) has **zero** endpoints to read, mint, reset, or obtain Lead credentials for `W1` (or any existing workspace).
   - Legacy `POST /api/v1/visitor-session` (and the `0006_actor_auth` backfill of existing `visitor_contexts`) provisions **only** an `engineer` actor (`ops-engineer-1`, `access_code_hash = NULL`) with no Lead actor or Lead credentials, guaranteeing legacy visitor sessions never grant Lead privileges.
3. **Defense-in-depth against self-approval:**
   - Role boundary (`engineer` gets `403` on Lead routes; `lead` gets `403` on Engineer routes) already separates the personas.
   - In addition, Task 6E Lead approval (`approve` and per-item `bulk-approve`) MUST enforce inside the commit transaction:
     - `current_actor.actor_id != revision.created_by_actor_id` (when non-null), AND
     - `current_actor.actor_id != validating_engineer_actor_id` (from the latest validation event on that revision).
   - Violation raises `403 SELF_APPROVAL_FORBIDDEN` (or marks that item `blocked` in `bulk-approve`).

### 7. Compatibility with Existing Visitor Sessions and Local HTTP Development

- **Cookie transport preserved:** `actor_sessions` uses the existing `get_cookie_policy(request)` helper:
  - HTTPS (`PUBLIC_ORIGIN=https://...`): `__Host-opspilot_visitor`, `Secure=True`, `HttpOnly=True`, `SameSite=Lax`, `Path=/`, no `Domain`.
  - Opt-in local HTTP (`ALLOW_INSECURE_LOCAL_HTTP=true` and `PUBLIC_ORIGIN` on `http://localhost` or `http://127.0.0.1`): `opspilot_visitor`, `Secure=False`, `HttpOnly=True`, `SameSite=Lax`, `Path=/`, no `Domain`.
  - Production/HTTPS never weakens cookie security flags even if `ALLOW_INSECURE_LOCAL_HTTP=true`.
- **Single active session cookie per browser:** Storing the `actor_sessions` token in the single `__Host-opspilot_visitor` / `opspilot_visitor` cookie prevents split-brain state across two cookies.
- **Exact `POST /api/v1/visitor-session` compatibility:**
  - Continues returning `201` (new) / `200` (existing valid cookie) with the exact JSON shape `{"visitor_context_id": UUID, "expires_at": UTC datetime}` so all existing frontend callers and `test_visitor_sessions.py` assertions remain valid.
  - Internally creates `VisitorContext` (populating `visitor_contexts.session_token_hash` for existing test assertions), provisions **only** `ops-engineer-1` (`engineer`, `access_code_hash = NULL`), and inserts the matching `ActorSession`. Legacy visitor sessions never grant Lead privileges or permit Lead login.
  - `CurrentVisitor` remains available as a compatibility wrapper returning `VisitorSession(visitor_context_id, expires_at)`, while new and updated domain routes use `CurrentActor` / `require_role(...)`.
- **Workspace vs session expiry & logout:**
  - `actor_sessions.expires_at = min(now + VISITOR_SESSION_TTL_SECONDS, visitor_contexts.expires_at)` so logging in later cannot extend a workspace past its D-019 absolute deadline.
  - `POST /api/v1/auth/logout` sets `actor_sessions.invalidated_at = clock()` and clears the caller's cookie **without** invalidating `visitor_contexts.invalidated_at`, so another actor in the same workspace remains unaffected.
  - Setting `visitor_contexts.invalidated_at` (e.g., workspace revocation or existing D-019 tests) invalidates all sessions in that workspace immediately.

### 8. Required Migrations, API Contracts, and Acceptance Tests for Task 6A

#### Task 6A Scope Boundary (Backend-Only)

- **Task 6A is strictly backend-only.** It implements migration `0006_actor_auth`, server-side actor/session dependencies, `/api/v1/auth/*` endpoints, `GET /api/v1/investigations`, role guards on existing investigation/findings routes, and backend automated tests.
- **No frontend authentication or review UI** (`VisitorSessionPanel` updates, header actor/role indicator, Lead sign-in modal, or findings/review screens) is implemented in Task 6A; frontend auth/review work remains deferred to Tasks 6F/6G (or a separately authorized frontend increment).

#### Non-Production Identity Disclaimer

- This fictional, workspace-scoped actor identity system (`visitor_contexts`, `workspace_actors`, `actor_sessions`, and one-time `access_code`s) is a **minimal MVP mechanism for synthetic-data demonstration and portfolio learning**, **not production-grade identity management**.
- It intentionally omits real user accounts, password/MFA/SSO/OIDC authentication, directory/IdP synchronization, credential rotation/recovery workflows, brute-force rate-limiting infrastructure, fine-grained RBAC/ABAC, and compliance-grade key custody.

#### Migration Strategy (`0006_actor_auth`, `down_revision = "0005_ai_findings"`)

Note: Task 6A claims migration `0006_actor_auth`; Task 6B's revision/audit persistence migration (tentatively named `0006` in the earlier handoff) becomes `0007_human_findings_review`.

1. **Create `workspace_actors`:**
   - `actor_id` (`UUID`, PK)
   - `visitor_context_id` (`UUID`, `FK -> visitor_contexts.visitor_context_id ON DELETE RESTRICT`, `NOT NULL`, indexed)
   - `actor_ref` (`Text`, `NOT NULL`, `CHECK (actor_ref ~ '^[a-z0-9][a-z0-9._-]{1,63}$')`)
   - `display_name` (`Text`, `NOT NULL`, `CHECK (btrim(display_name) <> '' AND length(display_name) <= 120)`)
   - `role` (`Text`, `NOT NULL`, `CHECK (role IN ('engineer', 'lead'))`)
   - `access_code_hash` (`LargeBinary`, nullable, `CHECK (access_code_hash IS NULL OR octet_length(access_code_hash) = 32)`)
   - `created_at` (`DateTime(timezone=True)`, `server_default=func.now()`, `NOT NULL`)
   - `disabled_at` (`DateTime(timezone=True)`, nullable, `CHECK (disabled_at IS NULL OR disabled_at >= created_at)`)
   - Constraints: `UQ (visitor_context_id, actor_ref)`, `UQ (visitor_context_id, actor_id)`, `UQ (actor_id, role)`, and partial unique index `uq_workspace_actors_access_code_hash` on `(access_code_hash) WHERE access_code_hash IS NOT NULL`.
2. **Create `actor_sessions`:**
   - `session_id` (`UUID`, PK)
   - `visitor_context_id` (`UUID`, `NOT NULL`)
   - `actor_id` (`UUID`, `NOT NULL`)
   - `session_token_hash` (`LargeBinary`, `UNIQUE`, `NOT NULL`, `CHECK (octet_length(session_token_hash) = 32)`)
   - `created_at` (`DateTime(timezone=True)`, `server_default=func.now()`, `NOT NULL`)
   - `expires_at` (`DateTime(timezone=True)`, `NOT NULL`, `CHECK (expires_at > created_at)`)
   - `invalidated_at` (`DateTime(timezone=True)`, nullable, `CHECK (invalidated_at IS NULL OR invalidated_at >= created_at)`)
   - Composite FK: `(visitor_context_id, actor_id) REFERENCES workspace_actors(visitor_context_id, actor_id) ON DELETE RESTRICT`.
   - Index on `(visitor_context_id, actor_id)`.
3. **Alter `visitor_contexts`:**
   - `ALTER COLUMN session_token_hash DROP NOT NULL` (retain unique index and 32-byte length check when non-null).
4. **Idempotent Backfill in `0006_actor_auth.upgrade()`:**
   - For every existing `visitor_contexts` row lacking a `workspace_actors` row:
     - Insert `ops-engineer-1` (`role='engineer'`, `access_code_hash=NULL`).
     - Insert an `actor_sessions` row copying `(visitor_context_id, actor_id, session_token_hash, created_at, expires_at, invalidated_at)` where `session_token_hash IS NOT NULL`.
   - Preserves all live local-dev sessions and all 23 existing tables (`0001`–`0005`).

#### Task 6A API Contracts (`/api/v1`, `Cache-Control: no-store`, `X-Request-ID`)

- **`POST /api/v1/auth/workspaces`** (`Origin` + `X-OpsPilot-Request: 1` + JSON `{}`, `extra="forbid"`, `201`):
  - Atomically creates `VisitorContext` (`session_token_hash=NULL`), `ops-engineer-1` (`engineer`), `payments-lead-1` (`lead`), generates two 256-bit `access_code`s (storing SHA-256 digests only), and creates an initial `ActorSession` for `ops-engineer-1`, setting the `HttpOnly` cookie after commit.
  - Returns `WorkspaceBootstrap`: `{visitor_context_id, expires_at, current_session: AuthSession, actor_credentials: [{actor_id, actor_ref, display_name, role, access_code}]}`.
  - Never touches or reveals credentials of any existing workspace even if the caller already holds a cookie.
- **`POST /api/v1/auth/login`** (`Origin` + `X-OpsPilot-Request: 1` + JSON `{visitor_context_id: UUID, actor_ref: str, access_code: str}`, `extra="forbid"`, `200`):
  - Validates `access_code` syntax (`TOKEN_PATTERN`), verifies `(visitor_context_id, actor_ref, sha256(access_code))` against active `workspace_actors` + unexpired/uninvalidated `visitor_contexts`. Uniform `401 AUTHENTICATION_FAILED` on any failure.
  - If the request carried an existing valid `ActorSession` cookie, invalidates that prior `ActorSession` only (never `visitor_contexts`) inside the same transaction.
  - Inserts new `ActorSession` (capped by `visitor_contexts.expires_at`), sets the `HttpOnly` cookie after commit, and returns `AuthSession`.
- **`POST /api/v1/auth/logout`** (`Origin` + `X-OpsPilot-Request: 1` + JSON `{}`, `extra="forbid"`, `200`):
  - Requires `CurrentActor` (`401` otherwise). Marks `actor_sessions.invalidated_at = clock()` inside the transaction, clears the cookie, and returns `{"logged_out": true}`.
- **`GET /api/v1/auth/session`** (`200`):
  - Requires `CurrentActor`. Returns `AuthSession`: `{session_id, visitor_context_id, actor_id, actor_ref, display_name, role, expires_at}`.
- **`GET /api/v1/investigations`** (`200`):
  - Requires `CurrentActor` (`engineer` or `lead`). Returns `{investigations: [{investigation_id, incident_id, incident_ref, state_id, draft_version, created_at}]}` filtered strictly by `Investigation.visitor_context_id == current_actor.visitor_context_id`.
- **Existing routes updated in Task 6A:**
  - `POST /api/v1/investigations`: requires `engineer` (`403 ROLE_FORBIDDEN` for `lead`).
  - `POST /api/v1/investigations/{id}/threads/{thread}/cases/{case}/finding-generations`: requires `engineer` (`404` for foreign workspace, `403 ROLE_FORBIDDEN` for same-workspace `lead`).
  - `GET /incidents/{ref}`, `GET .../workspace`, `GET .../cases`, `POST .../evidence-requests`, `GET .../findings`: accept `CurrentActor` (`engineer` or `lead` in the owning workspace; `404` for foreign workspace).

#### Task 6A Acceptance Tests

1. **Migration & Backfill:** Upgrade empty schema (`0001` → `0006`) and populated `0005` schema; verify `alembic check`, pre-existing `visitor_contexts` rows backfill into `workspace_actors` + `actor_sessions` and remain usable, and composite FK rejects cross-workspace `(visitor_context_id, actor_id)` session inserts.
2. **Workspace Bootstrap & Multi-Actor Access:** `POST /auth/workspaces` creates workspace + 2 actors, sets Engineer cookie, returns one-time credentials without storing plaintext `access_code` or leaking tokens in logs/responses; Client B logs in as Lead via `POST /auth/login`; both inspect the same `investigation_id` via `GET /investigations`, `GET .../workspace`, `GET .../cases`, `POST .../evidence-requests`, and `GET .../findings`.
3. **401 / 403 / 404 Authorization Matrix:**
   - Unauthenticated calls to `/auth/session`, `/auth/logout`, `/investigations`, and domain routes return `401` (`SESSION_REQUIRED` / `SESSION_INVALID` / `SESSION_EXPIRED`).
   - Foreign-workspace (`W2`) Engineer and Lead probing `W1`'s `investigation_id` on both Engineer-only and Lead-only routes receive **`404 NOT_FOUND`**, never `403`.
   - Same-workspace (`W1`) Lead calling `POST /investigations` or `POST .../finding-generations` receives **`403 ROLE_FORBIDDEN`**.
   - Same-workspace (`W1`) Engineer calling a Lead-guarded dependency route (`require_role("lead")`) receives **`403 ROLE_FORBIDDEN`**.
4. **Anti-Impersonation, Anti-Escalation, & Secret Hygiene:**
   - Forged `X-Actor-Role`, `X-Actor-Id`, `role`, `actor_id`, or `visitor_context_id` headers/query/body fields are rejected (`422`) or ignored.
   - Wrong `access_code`, wrong `visitor_context_id`, disabled actor, or replaying `access_code_hash` returns uniform `401 AUTHENTICATION_FAILED`.
   - Authenticated Engineer sessions cannot mint, read, or reset Lead credentials on any existing workspace; legacy `POST /api/v1/visitor-session` and `0006_actor_auth` backfilled sessions cannot login or escalate to `lead`.
   - `access_code` values, raw session cookies, and SHA-256 digests never appear in `GET /auth/session`, `GET /investigations`, error `details`, or application/validation/SQL logs (`caplog`).
   - `POST /auth/login` in Browser B does not invalidate Browser A's Engineer session; `POST /auth/logout` in Browser A invalidates only Browser A's session while Browser B remains active.
   - Session expiry is capped at `visitor_contexts.expires_at` and rechecked before response and inside write transactions.
5. **Compatibility & Local HTTP Dev:**
   - Existing 479 backend tests (including all `test_visitor_sessions.py` assertions) pass unchanged.
   - `ALLOW_INSECURE_LOCAL_HTTP=true` with `http://localhost:3000` issues/clears `opspilot_visitor` without `Secure` for `/auth/workspaces`, `/auth/login`, and `/auth/logout`, while HTTPS retains `__Host-opspilot_visitor` with `Secure`.

---

## Consequences

- **Easier:**
  - Tasks 6B–6E gain stable, workspace-scoped `actor_id` and `role` primitives (`CurrentActor`, `require_role("engineer" | "lead")`) and DB-enforced `(actor_id, role)` integrity for `finding_review_events`.
  - Both local evaluation and hosted multi-visitor demos support true two-actor workflows on the same investigation with zero cross-workspace leakage.
- **Harder / New responsibilities:**
  - Frontend Tasks 6F/6G must extend the session panel to use `/auth/workspaces`, `/auth/login`, `/auth/logout`, and `/auth/session` and display the one-time Lead sign-in code in memory/UI during workspace setup (Task 6A remains backend-only).
  - Because `access_code` values are never stored in plaintext and never recoverable via ordinary APIs, losing the Lead `access_code` before logging in requires starting a new shared workspace (consistent with D-019).
  - Because this fictional MVP auth is explicitly not production-grade identity management, any transition beyond synthetic demo use requires replacing `workspace_actors`/`access_code` with a real IdP/SSO or credential system.
- **Risks & Mitigations:**
  - *Risk: Single evaluator forgets to copy Lead `access_code` when using one browser.* Mitigation: In Task 6F/6G UI, display a clear "Copy Lead sign-in details" disclosure during workspace creation and warn that it cannot be recovered after closing/reloading (matching D-019).
  - *Risk: Migration `0006` ordering conflict with earlier handoff doc.* Mitigation: Explicitly rename Task 6A migration to `0006_actor_auth` and Task 6B migration to `0007_human_findings_review`.
  - *Risk: Legacy `/visitor-session` users expecting Lead handoff.* Mitigation: Keep `/visitor-session` documented as single-actor anonymous Engineer mode; Task 6F/6G UI switches workspace creation to `/auth/workspaces`.

---

## Validation plan

- Owner reviews and accepts this proposed ADR as **D-037** in `docs/DECISION_LOG.md` before implementation begins.
- Task 6A implements `0006_actor_auth`, `actor_auth` / `visitor_sessions` updates, `/api/v1/auth/*` endpoints, `GET /api/v1/investigations`, role guards on existing investigation/findings routes, and the Task 6A acceptance test suite above.
- Verify with `pytest`, `alembic current`, `alembic check`, `ruff check`, and `ruff format --check` (zero live AI provider calls).

---

## Revisit trigger

- Requirement for real persistent user accounts, multi-workspace user memberships, SSO/OIDC, or credential rotation/recovery for non-synthetic deployments.
- Requirement for more than two operational roles (e.g., Workspace Admin or Auditor) or fine-grained per-investigation ACLs beyond workspace-level roles.
