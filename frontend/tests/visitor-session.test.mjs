import assert from "node:assert/strict";
import { test, mock } from "node:test";
import { bootstrapVisitorSession } from "../lib/visitor-session.ts";

const session = { visitor_context_id: "00000000-0000-4000-8000-000000000001", expires_at: "2026-11-14T00:00:00Z" };

test("concurrent bootstrap callers share one same-origin POST", async () => {
  let finish;
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async (path, options) => {
    count++;
    assert.equal(path, "/api/v1/visitor-session");
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.headers["X-OpsPilot-Request"], "1");
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.equal(options.body, "{}");
    await new Promise(resolve => { finish = resolve; });
    return new Response(JSON.stringify(session), { status: 201 });
  });
  try {
    const first = bootstrapVisitorSession();
    const second = bootstrapVisitorSession();
    assert.equal(first, second);
    assert.equal(count, 1);
    finish();
    assert.deepEqual(await first, { session, created: true });
    assert.deepEqual(await second, { session, created: true });
  } finally { fetch.mock.restore(); }
});

test("a failed bootstrap can be retried and an existing session is recognized", async () => {
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async () => {
    count++;
    return count === 1 ? new Response("unavailable", { status: 503 }) :
      new Response(JSON.stringify(session), { status: 200 });
  });
  try {
    await assert.rejects(bootstrapVisitorSession(), /HTTP 503/);
    assert.deepEqual(await bootstrapVisitorSession(), { session, created: false });
    assert.equal(count, 2);
  } finally { fetch.mock.restore(); }
});

test("unexpected session payloads are rejected without logging them", async () => {
  const fetch = mock.method(globalThis, "fetch", async () =>
    new Response("{}", { status: 201 }));
  try { await assert.rejects(bootstrapVisitorSession(), /unexpected session response/); }
  finally { fetch.mock.restore(); }
});
