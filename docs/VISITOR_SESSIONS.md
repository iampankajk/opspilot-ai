# D-019 anonymous visitor sessions

Task 2 implements session bootstrap and a reusable authentication dependency on the existing
`visitor_contexts` table. No migration or dependency was added. Migration head remains
`0001_ownership_catalog`. Investigation creation and investigation-level authorization are
not implemented by this task.

## Contract and lifecycle

Use the existing [local HTTPS setup](FOUNDATION_SETUP.md). On the foundation page, select
**Start or resume demo session**. The browser POSTs `{}` to `/api/v1/visitor-session`, with
`Content-Type: application/json` and `X-OpsPilot-Request: 1`; the browser supplies its Origin.
The frontend shares one in-flight bootstrap promise per tab and disables the button while
pending. It sends no owner ID, never reads the secret cookie, and uses no localStorage identity.

- Valid cookie: **200**, same public visitor reference and UTC expiry; no replacement cookie
  or extension of the stored lifetime.
- Missing, malformed, unknown, expired, or invalidated cookie on this explicit bootstrap:
  **201**, a new random token and new owner. Earlier rows are retained. A supplied cookie
  value is never registered as a new credential.
- Protected request: missing cookie gives **401 `SESSION_REQUIRED`**; malformed, unknown,
  or invalidated credentials give **401 `SESSION_INVALID`**; expired credentials give
  **401 `SESSION_EXPIRED`**. Invalid/expired cookies are cleared. Authentication never
  automatically creates a visitor or recovers access from a public UUID.
- Invalid/missing/extra body fields: **422 `VALIDATION_ERROR`**. POST origin, custom-header,
  JSON media type, and 4 KiB controls remain in force. No context is created on rejection.
- Database failure: **503 `DATABASE_UNAVAILABLE`**, safe detail, request ID, and retryable flag.
  A failed creation transaction issues no cookie. The UI permits an explicit retry. If a
  response/cookie is lost, access cannot be recovered using its public visitor reference.

Successful JSON contains only `visitor_context_id` and `expires_at`. All API responses use
`Cache-Control: no-store` and `X-Request-ID`. Never dump Cookie/Set-Cookie headers or connection
parameters into logs, screenshots, or CLI output. The new secret is transported only in
Set-Cookie, not the JSON body or JavaScript-accessible storage.

## Storage and cookie

| Item | Behavior |
|---|---|
| Token | `secrets.token_urlsafe(32)`: 32 random bytes, represented as 43 base64url characters without padding. |
| Stored credential | Unique binary 32-byte SHA-256 digest; no plaintext token column. |
| Cookie | `__Host-opspilot_visitor`; Secure; HttpOnly; SameSite=Lax; Path=/; no Domain. |
| Lifetime | `VISITOR_SESSION_TTL_SECONDS`, a positive integer defaulting to **86400 seconds**. |
| Expiry | `created_at + configured TTL`, stored once; configuration changes and reuse do not extend old rows. |
| Browser expiry | Max-Age rounded down to remaining seconds and absolute Expires. A sub-second remainder is rejected rather than issuing a useful cookie beyond the deadline. |
| Invalid/expired cookie clearing | Same name/path, Secure/HttpOnly/SameSite flags, Max-Age=0 and expired date; no Domain. |

Application expiry is checked after the database query, independently of browser expiry.
The database server's timezone does not change API serialization: `expires_at` is normalized
to ISO 8601 UTC for both creation and reuse. Invalidating access does not delete or reassign
the stable visitor record or its future children.

## Implementation concepts

The core implementation is `backend/app/visitor_sessions.py`:

1. `secrets.token_urlsafe(32)` explicitly requests 256 bits from the operating system's secure
   randomness source. Python's ordinary simulation-oriented `random` generator is unsuitable
   for this credential. See the [Python secrets documentation](https://docs.python.org/3/library/secrets.html).
2. `hashlib.sha256(token.encode("ascii")).digest()` derives the exact binary value indexed in
   PostgreSQL. With an unpredictable 256-bit token, a fast cryptographic digest is appropriate;
   this is not a scheme for hashing human-chosen passwords. The stored digest cannot be replayed
   as the cookie, because the server hashes received cookie values before lookup.
3. `with Session(...), db.begin()` scopes database work and makes commit/rollback explicit.
   `flush()` inserts the new row and assigns its application-generated UUID. Cookie issuance
   occurs only after the transaction commits successfully.
4. `authenticate()` checks token syntax, finds the matching digest, and checks invalidation and
   server expiry. It returns only an immutable public visitor identity. It accepts no caller-
   supplied visitor ID as proof of access. SQL parameters are hidden by the existing engine.
5. `CurrentVisitor` is the dependency alias future routes should use. Before `yield`, it
   resolves authentication; after the handler, it queries again to reject expiry/invalidation
   before protected data is sent. `scope="function"` makes that second check run before the
   response leaves FastAPI, rather than after sending it. See [FastAPI dependency scopes](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope).

The browser cookie holds the bearer secret and tells the browser when/where to send it. The
database visitor record holds a stable owner UUID, digest, creation/expiry, and optional
invalidation timestamp. Its UUID is a reference, not a credential. FastAPI authenticates a
later request by hashing the automatically sent cookie and resolving its record again;
there is no process-memory identity registry or browser-provided owner override.

For future writes, the final dependency check is **not** a rollback mechanism for a handler
that already committed changes. Investigation services must check the current authenticated
visitor, owning investigation, state/version, and session validity inside their transaction
before committing. They must return the same safe 404 for foreign and unknown resources.
Those routes, ownership-aware queries, composite state constraints, and concurrency tests
remain part of later approved tasks.

## Verification — 13 November 2026

From `backend/`:

```sh
.venv/bin/python -m pytest -q
.venv/bin/alembic current
.venv/bin/alembic check
.venv/bin/ruff check app alembic tests
.venv/bin/ruff format --check app alembic tests
.venv/bin/python -m pip check
```

Observed: **50 backend tests passed**, no skips; head `0001_ownership_catalog`; no new upgrade
operations; lint/format checks passed; no broken Python requirements. One upstream Starlette
deprecation warning remains for the legacy httpx TestClient adapter. Tests cover cookie flags,
hash-only storage, lifetime, reuse, missing/malformed/unknown/expired/invalidated credentials,
client-ID spoofing, separate cookie jars, rejection of identity overrides, late expiry before
protected response, transaction failure/rollback, retry, TTL configuration changes, and absent
test routes in the normal app. Database-backed tests use the dedicated test database and
roll back their session writes.

From `frontend/`, after selecting Node 22 with `nvm use`:

```sh
npm test
npm run typecheck
npm run build
```

Observed: **3 frontend tests passed** (one in-flight bootstrap, retry/reuse, unexpected response),
TypeScript checking passed, and production build passed. Node's built-in test runner is used;
no test framework dependency was added.

### Repeatable real-browser checks

Stop only your own normal backend process. From `backend/`, temporarily launch:

```sh
.venv/bin/uvicorn browser_harness:app --app-dir tests --host 127.0.0.1 --port 8000 --no-access-log
```

Keep Next.js running over HTTPS and open
[the test-only browser page](https://localhost:3000/api/v1/_session-tests). Select **Run session checks**.
The harness refuses a database name not ending in `_test`, uses only `TEST_DATABASE_URL`, and
does not run migrations, delete rows, or reset a database. Its test cookies and virtual clock
belong only to that explicitly launched test application. It creates a few synthetic visitor
rows in the test database, retained for inspection. Never deploy or run this harness as the
normal application. Stop it after checking, then restore the usual `app.main:app` command.

Observed: **all 14 browser checks passed** through the actual Next.js HTTPS proxy: missing
cookie and client-ID rejection; creation; HttpOnly/Set-Cookie JavaScript inaccessibility;
Secure host-cookie acceptance and forwarding; unchanged reuse; unknown-token rejection and
cookie clearing; fresh context; UUID impersonation rejection; invalidation; server expiry
while the browser still sends its cookie; expired-cookie clearing; and explicit new bootstrap.
Expiry uses a server-only test clock advanced 25 hours; this is not a 24-hour wall-clock test.
Browser contexts are created sequentially in this page; automated backend tests additionally
use independent cookie jars. Exact flags, SameSite, Path, and absence of Domain are checked
in the automated API tests. Full investigation resource isolation is not yet testable.

The normal application was restored afterward. Its page created then reused a session with
unchanged public reference/expiry, and foundation readiness stayed Connected. Test-only
probe/control routes are not mounted in `app.main:app`. No new protected product route,
login, recovery, investigation creation, migration, or AI workflow was introduced. Task 3
has not been started.
