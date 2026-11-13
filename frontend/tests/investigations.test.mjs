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
