import assert from "node:assert/strict";
import { test, mock } from "node:test";
import { createInvestigation, loadIncident, loadWorkspace, parseWorkspace } from "../lib/investigations.ts";

const id = "00000000-0000-4000-8000-000000000001";
const incident = { incident_id: id, incident_ref: "INC-2026-1042", title: "Synthetic incident",
  description: null, category: null, severity: "SEV-2", region: "APAC", synthetic: true,
  source_alert_record_id: "SYN-PD-ALERT-001",
  incident_time: { role: "incident_alert", raw: "10:30 AM SGT", timezone: "Asia/Singapore",
    precision: "second", utc_lower: "2026-10-20T02:30:00Z", utc_upper: "2026-10-20T02:30:00Z", missing_reason: null } };
const dataset_version = { dataset_version_id: id, version_label: "synthetic-payments-v0.1", fixture_digest: "a".repeat(64) };
const workspace = { investigation_id: id, state_id: id, draft_version: 0, incident, dataset_version,
  threads: [{ thread_kind: "payment_failures", label: "Payment failures", case_count: 1 },
    { thread_kind: "possible_duplicates", label: "Possible duplicates", case_count: 1 }] };

test("create sends only incident_id with the same-origin POST boundary", async () => {
  const fetch = mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, "/api/v1/investigations");
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.headers["X-OpsPilot-Request"], "1");
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(options.body), { incident_id: id });
    return new Response(JSON.stringify(workspace), { status: 201 });
  });
  try { assert.deepEqual(await createInvestigation(id), workspace); }
  finally { fetch.mock.restore(); }
});

test("incident and workspace retrieval are uncached GETs with no identity override", async () => {
  const fetch = mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(options.method, "GET"); assert.equal(options.cache, "no-store");
    assert.equal(options.body, undefined);
    return new Response(JSON.stringify(path.includes("/incidents/") ? { incident, dataset_version } : workspace));
  });
  try {
    assert.deepEqual(await loadIncident("INC-2026-1042"), { incident, dataset_version });
    assert.deepEqual(await loadWorkspace(id), workspace);
  } finally { fetch.mock.restore(); }
});

test("expired authentication is surfaced without auto-bootstrap or replacement", async () => {
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async () => {
    count++;
    return new Response(JSON.stringify({ error: { code: "SESSION_EXPIRED" } }), { status: 401 });
  });
  try {
    await assert.rejects(loadWorkspace(id), error => error.code === "SESSION_EXPIRED" && error.status === 401);
    assert.equal(count, 1);
  } finally { fetch.mock.restore(); }
});

test("missing/duplicate threads and invalid case counts are rejected", () => {
  for (const threads of [[], [workspace.threads[0], workspace.threads[0]],
    [workspace.threads[0], { ...workspace.threads[1], case_count: -1 }]]) {
    assert.throws(() => parseWorkspace({ ...workspace, threads }), /unexpected workspace/);
  }
});

test("thread cases require the selected state and support empty results", async () => {
  const { loadCases } = await import("../lib/investigations.ts");
  const data = { investigation_id: id, state_id: id, draft_version: 1, thread_kind: "possible_duplicates", cases: [] };
  const fetch = mock.method(globalThis, "fetch", async (path, options) => {
    assert.equal(path, `/api/v1/investigations/${id}/threads/possible_duplicates/cases?state_id=${id}`);
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.cache, "no-store"); assert.equal(options.method, "GET");
    assert.equal(options.body, undefined);
    return new Response(JSON.stringify(data));
  });
  try { assert.deepEqual(await loadCases(id, id, "possible_duplicates"), data); }
  finally { fetch.mock.restore(); }
});

test("case parser rejects a response for another state, investigation, or thread", async () => {
  const { parseCaseList } = await import("../lib/investigations.ts");
  const expected = { investigation_id: id, state_id: id, thread_kind: "payment_failures" };
  const data = { ...expected, draft_version: 0, cases: [] };
  for (const change of [{ state_id: "other" }, { investigation_id: "other" }, { thread_kind: "possible_duplicates" },
    { draft_version: -1 }, { cases: null }]) {
    assert.throws(() => parseCaseList({ ...data, ...change }, expected), /unexpected case-list/);
  }
  assert.deepEqual(parseCaseList(data, expected).cases, []);
});

test("reported money stays exact text and candidate order is not promoted to reported order", async () => {
  const { parseCaseList } = await import("../lib/investigations.ts");
  const expected = { investigation_id: id, state_id: id, thread_kind: "possible_duplicates" };
  const c = { case_id: "case-duplicate-001", case_reference: "CASE-DUP-001", primary_report_record_id: "SYN-ZD-TICKET-002",
    customer_ref: "SYN-CUST-002", reported_order_ref: null,
    related_order_refs: [{ value: "SYN-ORD-002", association: "candidate", basis_record_id: "SYN-ZD-HANDOFF-001" }],
    reported_issue: "Customer reports two charges", reported_money: { amount: "120.00", currency: "SGD" },
    reported_at: incident.incident_time, payment_state: null, investigation_progress: "not_started" };
  const data = { ...expected, draft_version: 0, cases: [c] };
  assert.deepEqual(parseCaseList(data, expected).cases[0], c);
  for (const change of [{ reported_money: { amount: 120, currency: "SGD" } },
    { related_order_refs: [{ ...c.related_order_refs[0], association: "verified" }] },
    { investigation_progress: "resolved" }]) {
    assert.throws(() => parseCaseList({ ...data, cases: [{ ...c, ...change }] }, expected), /unexpected case-list/);
  }
});

test("case failures and stale selections permit an explicit retry", async () => {
  const { loadCases } = await import("../lib/investigations.ts");
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async () => {
    count++;
    return count === 1 ? new Response(JSON.stringify({ error: { code: "STALE_STATE" } }), { status: 409 }) :
      new Response(JSON.stringify({ investigation_id: id, state_id: id, draft_version: 0, thread_kind: "payment_failures", cases: [] }));
  });
  try {
    await assert.rejects(loadCases(id, id, "payment_failures"), error => error.code === "STALE_STATE" && /Reload/.test(error.message));
    assert.deepEqual((await loadCases(id, id, "payment_failures")).cases, []);
    assert.equal(count, 2);
  } finally { fetch.mock.restore(); }
});
