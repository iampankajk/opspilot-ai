import assert from "node:assert/strict";
import { test, mock } from "node:test";
import { evidenceGroups, inspectEvidence, outcomeMessage, parseCaseEvidence } from "../lib/evidence.ts";

const scope = { investigation_id: "investigation", state_id: "state", thread_kind: "payment_failures", case_id: "case" };
const basis = { category: "documented_lookup", explanation: "Candidate from lookup; not a verified charge.", matched_fields: { order: "candidate" }, basis_record_id: null };
const record = { evidence_record_id: "record", source_key: "stripe", source_name: "Original provider", record_type: "provider_extract",
  source_record_reference: null, synthetic: true,
  fixture_provenance: { version_label: "v0.1", fixture_record_id: "record", origin: "Constructed synthetic fixture" },
  timestamps: [{ role: "event", raw: "10:30 SGT", timezone: "Asia/Singapore", precision: "minute", utc_lower: null, utc_upper: null, missing_reason: null }],
  payload: { capture: "one observed; completeness unverified" }, case_association: basis };
function response() {
  return { ...scope, request_id: "transport", evidence_request_id: "persisted", draft_version: 2, status: "completed",
    groups: evidenceGroups.map(g => ({ group_kind: g.kind, sources: g.sources.map(key => ({
      source_key: key, source_name: key, execution_status: "completed", availability: "included",
      match_status: key === "stripe" ? "matches" : "no_matches", returned_count: key === "stripe" ? 1 : 0,
      records: key === "stripe" ? [structuredClone(record)] : [], scope: "case", completeness: "unverified",
      limitations: ["No bank evidence constructed"], error_code: null,
    })) })), relationships: [] };
}

test("evidence POST is bounded, authenticated, scoped and explicitly retryable", async () => {
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async (path, options) => {
    count++;
    assert.equal(path, "/api/v1/investigations/investigation/threads/payment_failures/cases/case/evidence-requests");
    assert.equal(options.method, "POST"); assert.equal(options.credentials, "same-origin"); assert.equal(options.cache, "no-store");
    assert.equal(options.headers["X-OpsPilot-Request"], "1"); assert.equal(options.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(options.body), { state_id: "state", expected_draft_version: 2, retry_of_request_id: "old" });
    return new Response(JSON.stringify(response()));
  });
  try { assert.equal((await inspectEvidence(scope, 2, "old")).evidence_request_id, "persisted"); assert.equal(count, 1); }
  finally { fetch.mock.restore(); }
});

test("inspection parser preserves original provenance, candidate basis, and timestamp precision", () => {
  const data = parseCaseEvidence(response(), scope);
  assert.deepEqual(data.groups[1].sources[0].records[0], record);
});

test("all four groups and all six explicit source outcomes are mandatory", () => {
  for (const mutate of [d => d.groups.pop(), d => d.groups[2].sources.pop(),
    d => d.groups[0].sources[0].source_key = "stripe", d => d.groups.reverse(),
    d => d.groups[0].sources.push(d.groups[0].sources[0])]) {
    const data = response(); mutate(data); assert.throws(() => parseCaseEvidence(data, scope), /unexpected evidence/);
  }
});

test("response isolation checks investigation, state, thread, and case", () => {
  for (const key of Object.keys(scope)) {
    assert.throws(() => parseCaseEvidence({ ...response(), [key]: "other" }, scope), /unexpected evidence/);
  }
});

test("zero matches, missing coverage, and failed source remain distinct", () => {
  const data = response(); const empty = data.groups[2].sources[0];
  assert.match(outcomeMessage(empty), /No matching records.*for this case/);
  const gap = { ...empty, availability: "not_constructed", match_status: "not_evaluated", returned_count: null };
  assert.match(outcomeMessage(gap), /not constructed.*Not evaluated/);
  const failed = { ...empty, execution_status: "failed", match_status: "not_evaluated", returned_count: null, error_code: "SOURCE_RETRIEVAL_FAILED" };
  assert.match(outcomeMessage(failed), /retrieval failed.*unknown.*Retry/);
  data.status = "partial"; data.groups[2].sources[0] = failed;
  assert.equal(parseCaseEvidence(data, scope).status, "partial");
  data.groups[2].sources[0].returned_count = 0;
  assert.throws(() => parseCaseEvidence(data, scope), /unexpected evidence/);
});

test("incomplete counts, duplicate records and dangling relationships are rejected", () => {
  for (const mutate of [d => d.groups[1].sources[0].returned_count = 2,
    d => d.groups[1].sources[0].records[0].timestamps[0].precision = "invented",
    d => d.groups[1].sources[0].records.push(d.groups[1].sources[0].records[0]),
    d => d.relationships.push({ relationship_id: "rel", from_record_id: "record", to_record_id: "foreign", basis, attribution: "fixture", limitations: [] })]) {
    const data = response(); mutate(data); assert.throws(() => parseCaseEvidence(data, scope), /unexpected evidence/);
  }
});

test("all-source failure and stale version return safe history details without automatic retry", async () => {
  let count = 0;
  const fetch = mock.method(globalThis, "fetch", async () => {
    count++;
    return new Response(JSON.stringify({ error: { code: count === 1 ? "EVIDENCE_RETRIEVAL_FAILED" : "STALE_DRAFT_VERSION",
      details: { evidence_request_id: "failed-request", draft_version: 2, state_id: "state", secret: "must not propagate" } } }), { status: count === 1 ? 503 : 409 });
  });
  try {
    await assert.rejects(inspectEvidence(scope, 0), e => e.code === "EVIDENCE_RETRIEVAL_FAILED" &&
      e.details.evidence_request_id === "failed-request" && e.details.draft_version === 2 && e.details.secret === undefined);
    assert.equal(count, 1);
    await assert.rejects(inspectEvidence(scope, 0), e => e.code === "STALE_DRAFT_VERSION" && /Reload/.test(e.message));
    assert.equal(count, 2);
  } finally { fetch.mock.restore(); }
});

// Render the actual presentation component with existing TypeScript/React dependencies.
// This exercises loading/error/empty branches without introducing browser or DOM libraries.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../app/evidence-view.tsx", import.meta.url), "utf8");
let compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext } }).outputText;
compiled = compiled.replace('"react/jsx-runtime"', JSON.stringify(pathToFileURL(require.resolve("react/jsx-runtime")).href))
  .replace('"../lib/evidence.ts"', JSON.stringify(new URL("../lib/evidence.ts", import.meta.url).href));
const { EvidenceView } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const render = result => renderToStaticMarkup(createElement(EvidenceView, { result, history: [],
  selectedCase: { case_reference: "CASE-FAIL-001" }, onInspect() {} }));

test("actual view keeps four source groups visible during loading without showing zero matches", () => {
  const html = render({ status: "loading" });
  for (const group of evidenceGroups) assert.ok(html.includes(group.label.replaceAll("&", "&amp;")));
  assert.equal((html.match(/Loading source evidence/g) ?? []).length, 4);
  assert.match(html, /disabled=""/);
  assert.doesNotMatch(html, /No matching records|0 matching records/);
});

test("actual view renders an actionable error without representing it as no evidence", () => {
  const html = render({ status: "failed", message: "The request timed out. Retry explicitly." });
  assert.match(html, /role="alert"/); assert.match(html, /Retry evidence/);
  assert.equal((html.match(/Count unknown/g) ?? []).length, 4);
  assert.doesNotMatch(html, /No matching records/);
});

test("actual view preserves empty source sections, original payload and inline keyboard expansion", () => {
  const data = response();
  const html = render({ status: "ready", data });
  assert.match(html, /No matching records found in the available synthetic dataset for this case/);
  assert.match(html, /<details[^>]*><summary>/);
  assert.match(html, /Original provider/); assert.match(html, /Precision: minute/);
  assert.match(html, /Candidate from lookup/); assert.match(html, /one observed; completeness unverified/);
  assert.doesNotMatch(html, /<script|was charged twice|was charged only once/);
});

function relationshipNavigation() {
  const data = response();
  const destination = { ...structuredClone(record), evidence_record_id: "other-record" };
  data.groups[1].sources[0].records.push(destination);
  data.groups[1].sources[0].returned_count = 2;
  data.relationships = [{ relationship_id: "relation", from_record_id: "record", to_record_id: "other-record",
    basis, attribution: "synthetic relationship", limitations: [] }];
  // Inspect the actual rendered component tree to exercise the handler wired to each link.
  const tree = EvidenceView({ result: { status: "ready", data }, history: [],
    selectedCase: { case_reference: "CASE-FAIL-001" }, onInspect() {} });
  const elements = [];
  function visit(node) {
    if (Array.isArray(node)) return node.forEach(visit);
    if (!node || typeof node !== "object" || !node.props) return;
    elements.push(node); visit(node.props.children);
  }
  visit(tree);
  return { links: elements.filter(n => n.type === "a"), details: elements.filter(n => n.type === "details" && n.props.id) };
}

test("relationship links reveal either target and focus after native fragment navigation", t => {
  const frames = [];
  const original = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
  t.after(() => {
    if (original === undefined) delete globalThis.requestAnimationFrame;
    else globalThis.requestAnimationFrame = original;
  });
  const { links, details } = relationshipNavigation();
  const focus = mock.fn();
  const targets = details.map(d => ({ id: d.props.id, open: false, isConnected: true, querySelector: () => ({ focus }) }));
  for (const link of links) {
    const preventDefault = mock.fn();
    const event = { currentTarget: { getAttribute: () => link.props.href,
      closest: selector => { assert.equal(selector, ".evidence-panel"); return { querySelectorAll: () => targets }; } },
      button: 0, defaultPrevented: false, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, preventDefault };
    assert.equal(typeof link.props.onClick, "function");
    const previousCalls = focus.mock.callCount();
    link.props.onClick(event);
    assert.equal(targets.find(t => `#${t.id}` === link.props.href).open, true);
    assert.equal(preventDefault.mock.callCount(), 0); // URL fragment/scroll and keyboard activation remain native.
    assert.equal(focus.mock.callCount(), previousCalls); // Let the browser finish its default action first.
    frames.shift()(0);
    assert.equal(focus.mock.callCount(), previousCalls + 1);
  }
  assert.ok(targets.every(t => t.open)); // Opening another record never closes a previous target.
  assert.deepEqual(focus.mock.calls[0].arguments, [{ preventScroll: true }]);
  assert.ok(details.every(d => d.props.open === undefined && d.props.onToggle === undefined));
  // Native collapse remains possible; navigating to a manually collapsed record reveals it again.
  targets[0].open = false;
  links[0].props.onClick({ button: 0, currentTarget: { getAttribute: () => links[0].props.href,
    closest: () => ({ querySelectorAll: () => targets }) } });
  assert.equal(targets[0].open, true);
  targets[0].isConnected = false;
  const previousCalls = focus.mock.callCount();
  frames.shift()(0);
  assert.equal(focus.mock.callCount(), previousCalls); // An unmounted scope must not take focus back.
});

test("modified relationship clicks keep the browser's new-tab behavior without changing disclosures", () => {
  const { links } = relationshipNavigation();
  for (const changed of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
    const closest = mock.fn();
    links[0].props.onClick({ button: 0, currentTarget: { closest }, ...changed });
    assert.equal(closest.mock.callCount(), 0);
  }
});
