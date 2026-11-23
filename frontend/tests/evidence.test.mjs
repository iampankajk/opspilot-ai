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
  .replace('"../lib/evidence.ts"', JSON.stringify(new URL("../lib/evidence.ts", import.meta.url).href))
  .replace('"../lib/evidence-presentation.ts"', JSON.stringify(new URL("../lib/evidence-presentation.ts", import.meta.url).href));
const { EvidenceView } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const render = result => renderToStaticMarkup(createElement(EvidenceView, { result, history: [],
  selectedCase: { case_reference: "CASE-FAIL-001" }, onInspect() {} }));

test("actual view keeps four source groups visible during loading without showing zero matches", () => {
  const html = render({ status: "loading" });
  for (const group of evidenceGroups) assert.ok(html.includes(group.label.replaceAll("&", "&amp;")));
  assert.equal((html.match(/Loading source evidence/g) ?? []).length, 6);
  assert.match(html, /aria-disabled="true"/);
  assert.doesNotMatch(html, /No matching records|0 matching records/);
});

test("busy evidence action stays focusable but ignores repeated keyboard/pointer activation", () => {
  const inspect = mock.fn();
  for (const status of ["loading", "idle", "ready"]) {
    const tree = EvidenceView({ result: status === "ready" ? { status, data: response() } : { status },
      history: [], selectedCase: { case_reference: "CASE-FAIL-001" }, onInspect: inspect });
    const button = tree.props.children[0].props.children[1];
    assert.equal(button.props.disabled, undefined);
    assert.equal(button.props["aria-disabled"], status === "loading");
    button.props.onClick();
  }
  assert.equal(inspect.mock.callCount(), 2);
});

test("evidence has one persistent atomic status region and source-named native disclosures", () => {
  for (const status of ["idle", "loading", "failed", "ready"]) {
    const html = render(status === "ready" ? { status, data: response() } : { status, message: "Retry explicitly" });
    assert.equal((html.match(/role="status"/g) ?? []).length, 1);
    assert.match(html, /role="status" aria-atomic="true"/);
    assert.equal((html.match(/role="alert"/g) ?? []).length, status === "failed" ? 1 : 0);
    if (status === "loading") assert.match(html, /Retrieving case evidence\. Source counts are unknown/);
    if (status === "ready") assert.match(html, /<summary><span class="sr-only">Stripe \/ Payment Provider · <\/span>Records \(1\)/);
  }
});

test("actual view renders an actionable error without representing it as no evidence", () => {
  const html = render({ status: "failed", message: "The request timed out. Retry explicitly." });
  assert.match(html, /role="alert"/); assert.match(html, /Retry evidence/);
  assert.equal((html.match(/Evidence unavailable after retrieval error/g) ?? []).length, 6);
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
  const firstTarget = targets.find(t => `#${t.id}` === links[0].props.href);
  firstTarget.open = false;
  links[0].props.onClick({ button: 0, currentTarget: { getAttribute: () => links[0].props.href,
    closest: () => ({ querySelectorAll: () => targets }) } });
  assert.equal(firstTarget.open, true);
  firstTarget.isConnected = false;
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

test("retained panels use distinct record fragments scoped to the originating thread and case", () => {
  const data = response();
  data.relationships = [{ relationship_id: "self", from_record_id: "record", to_record_id: "record",
    basis, attribution: "synthetic", limitations: [] }];
  for (const prefix of ["payment_failures-case-a-", "possible_duplicates-case-b-"]) {
    const html = renderToStaticMarkup(createElement(EvidenceView, { result: { status: "ready", data }, history: [],
      selectedCase: { case_reference: "CASE" }, idPrefix: prefix, onInspect() {} }));
    assert.ok(html.includes(`id="evidence-${prefix}record"`));
    assert.ok(html.includes(`href="#evidence-${prefix}record"`));
    assert.equal(html.includes('href="#evidence-record"'), false);
  }
});

import { associationLabel, groupCount, recordSummary, summaryTimestamp } from "../lib/evidence-presentation.ts";
import { revealEvidenceRecord } from "../lib/evidence.ts";
function elements(node, result = []) {
  if (Array.isArray(node)) node.forEach(child => elements(child, result));
  else if (node?.props) { result.push(node); elements(node.props.children, result); }
  return result;
}
const viewNodes = data => elements(EvidenceView({ result: { status: "ready", data }, history: [],
  selectedCase: { case_reference: "CASE" }, onInspect() {} }));

test("six source identities and unknown counts exist before a request, with one explicit action", () => {
  for (const status of ["idle", "loading", "failed"]) {
    const html = render({ status, message: "Retrieval interrupted; retry explicitly." });
    assert.equal((html.match(/data-source=/g) ?? []).length, 6);
    assert.equal((html.match(/class="evidence-group"/g) ?? []).length, 4);
    assert.doesNotMatch(html, /0 returned records|null matching|No matching records/);
    assert.equal((html.match(/<button/g) ?? []).length, 1);
    if (status === "idle") assert.equal((html.match(/Not requested/g) ?? []).length, 6);
  }
});

test("controlled source outcomes keep retrieval, availability, match, completeness and counts independent", () => {
  const variants = [
    { availability: "not_included", text: /not included/ },
    { availability: "not_constructed", text: /not constructed/ },
    { availability: "unavailable", text: /unavailable/ },
    { availability: "included", text: /Source not evaluated/ },
    { execution_status: "failed", text: /Retrieval failed/ },
    { execution_status: "interrupted", text: /Retrieval interrupted/ },
  ];
  for (const { text, ...change } of variants) {
    const data = response();
    Object.assign(data.groups[2].sources[0], { match_status: "not_evaluated", returned_count: null, records: [], ...change });
    if (change.execution_status) data.status = "partial";
    const validated = parseCaseEvidence(data, scope);
    const node = viewNodes(validated).find(n => n.props["data-source"] === "loki");
    const local = renderToStaticMarkup(node);
    assert.match(local, text); assert.match(local, /Count unknown/);
    assert.match(local, /Evidence completeness: unverified/);
    assert.doesNotMatch(local, /0 matching|No matching records|null matching/);
    assert.equal(groupCount(data.groups[2].sources), "Count unknown");
    if (change.execution_status) assert.match(render({ status: "ready", data }), /Retrieval partial/);
  }
  for (const completeness of ["unverified", "known_partial", "verified_for_stated_scope", "not_applicable"]) {
    const data = response(); data.groups[1].sources[0].completeness = completeness;
    assert.ok(render({ status: "ready", data }).includes(`Evidence completeness: ${completeness.replaceAll("_", " ")}`));
  }
});

test("completed retrieval retains local provider and bank limitations without claiming complete evidence", () => {
  const data = response();
  data.groups[1].sources[0].limitations = ["Provider completeness is unverified.", "Bank/settlement evidence unavailable."];
  const node = viewNodes(data).find(n => n.props["data-source"] === "stripe");
  const html = renderToStaticMarkup(node);
  assert.match(html, /Retrieval completed/); assert.match(html, /Evidence completeness: unverified/);
  assert.match(html, /Provider completeness is unverified/); assert.match(html, /Bank\/settlement evidence unavailable/);
  assert.doesNotMatch(html, /<details|Complete evidence/);
});

test("readable unknown/nested fields and exact amounts precede a closed original-payload disclosure", () => {
  const data = response();
  const payload = data.groups[1].sources[0].records[0].payload = {
    "Internal attempt status": "Timeout; provider outcome initially unknown", "Amount/currency": "SGD 120.00",
    "Unfamiliar field": { exact: "001.2300", missing: null, flags: [false, 0, "<script>alert(1)</script>"] },
    "Idempotency key": "SYN-IDEM-DUP-001", "Settlement/bank posting evidence": "Not constructed",
  };
  const html = render({ status: "ready", data });
  assert.match(html, /<dt>Amount\/currency<\/dt><dd>SGD 120.00<\/dd>/);
  assert.match(html, /<dt>Unfamiliar field<\/dt>/); assert.match(html, /001.2300/); assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  const original = viewNodes(data).find(n => n.props.className?.includes("original-payload"));
  assert.equal(original.props.open, undefined);
  const pre = elements(original).find(n => n.type === "pre");
  assert.deepEqual(JSON.parse(pre.props.children), payload);
  assert.ok(html.indexOf("<dt>Amount/currency") < html.indexOf("Original payload (JSON)"));
  assert.equal(pre.props.tabIndex, 0);
});

test("source wording, timestamp roles/ranges and missing-time reasons remain exact", () => {
  const rec = structuredClone(record);
  rec.payload = { "Internal attempt status": "Succeeded" };
  assert.deepEqual(recordSummary(rec), { label: "Internal attempt status", value: "Succeeded" });
  rec.timestamps = [
    { ...record.timestamps[0], role: "Event timestamps", raw: "Other event times not constructed", precision: "unknown" },
    { ...record.timestamps[0], role: "Capture event time", raw: "10:17–10:18 SGT", precision: "minute_range" },
  ];
  assert.equal(summaryTimestamp(rec), rec.timestamps[1]);
  const data = response(); data.groups[1].sources[0].records = [rec];
  let html = render({ status: "ready", data });
  assert.match(html, /Capture event time: 10:17–10:18 SGT/); assert.match(html, /Precision: minute_range/);
  assert.match(html, /Other event times not constructed/);
  rec.timestamps = [{ ...record.timestamps[0], raw: null, timezone: null, precision: "unknown", missing_reason: "Event not timestamped" }];
  html = render({ status: "ready", data });
  assert.match(html, /event: Not supplied · Timezone: Unknown · Precision: unknown · Event not timestamped/);
  rec.timestamps = []; assert.match(render({ status: "ready", data }), /Source timestamp not supplied/);
});

test("contextual relationships retain category, attribution, basis and fields with accessible explanations", () => {
  const data = response();
  data.groups[1].sources[0].records.push({ ...structuredClone(record), evidence_record_id: "target" });
  data.relationships = [{ relationship_id: "r", from_record_id: "record", to_record_id: "target", basis,
    attribution: "Application-labelled synthetic association", limitations: ["A field match is not a verified charge."] }];
  const nodes = viewNodes(data), links = nodes.filter(n => n.type === "a");
  assert.equal(links.length, 2);
  for (const link of links) {
    const explanation = nodes.find(n => n.props.id === link.props["aria-describedby"]);
    assert.ok(explanation); assert.match(renderToStaticMarkup(explanation), /Documented lookup: Candidate from lookup/);
  }
  const html = render({ status: "ready", data });
  assert.match(html, /Application-labelled synthetic association/); assert.match(html, /A field match is not a verified charge/);
  assert.match(html, /<dt>order<\/dt><dd>candidate/);
  assert.match(html, /Category: documented_lookup/); assert.match(html, /Basis record: Not supplied/);
  assert.deepEqual(["direct_ref_match", "documented_lookup", "field_match", "temporal_context", "unverified"].map(associationLabel),
    ["Direct reference match", "Documented lookup", "Field match", "Temporal context", "Unverified association"]);
  data.relationships[0].to_record_id = "missing";
  assert.match(render({ status: "ready", data }), /Related record missing is unavailable in this response/);
});

test("relationship reveal opens enclosing source lists without closing any originating record", () => {
  const outer = { open: false, parentElement: null };
  const source = { open: false, parentElement: { closest: () => outer } };
  const target = { open: false, parentElement: { closest: () => source } };
  const origin = { open: true };
  revealEvidenceRecord(target);
  assert.ok(target.open && source.open && outer.open && origin.open);
});

test("seeded payload sets remain readable and intact, with each provider extract kept as one record", () => {
  const fixture = JSON.parse(readFileSync(new URL("../../backend/fixtures/synthetic-payments-v0.1.json", import.meta.url), "utf8"));
  for (const [i, seeded] of fixture.cases.entries()) {
    const data = response(); data.thread_kind = seeded.thread_kinds[0];
    for (const group of data.groups) for (const source of group.sources) {
      const originals = fixture.records.filter(r => seeded.evidence_record_ids.includes(r.record_id) && r.source_key === source.source_key);
      source.records = originals.map(r => ({ ...structuredClone(record), source_key: r.source_key, evidence_record_id: r.record_id,
        source_name: r.payload["Source system"], payload: r.payload }));
      source.returned_count = originals.length; source.match_status = originals.length ? "matches" : "no_matches";
    }
    assert.deepEqual(data.groups.map(g => g.sources.reduce((n, s) => n + s.returned_count, 0)), i ? [2, 1, 0, 3] : [1, 1, 2, 1]);
    const originals = viewNodes(data).filter(n => n.props.className?.includes("original-payload"));
    assert.equal(originals.length, seeded.evidence_record_ids.length);
    for (const original of originals) {
      assert.equal(original.props.open, undefined);
      const pre = elements(original).find(n => n.type === "pre");
      const id = pre.props["aria-label"].replace("Original payload for ", "");
      assert.deepEqual(JSON.parse(pre.props.children), fixture.records.find(r => r.record_id === id).payload);
    }
    if (i) assert.match(render({ status: "ready", data }), /Multiple payment attempts do not establish multiple customer charges/);
  }
});

test("possible-duplicate caution retains the financial-evidence gap before, during and after retrieval", () => {
  for (const result of [{ status: "idle" }, { status: "loading" }, { status: "failed", message: "Interrupted" }, { status: "ready", data: response() }]) {
    const html = renderToStaticMarkup(createElement(EvidenceView, { result, history: [], thread: "possible_duplicates",
      selectedCase: { case_reference: "CASE-DUP" }, onInspect() {} }));
    assert.match(html, /Multiple payment attempts do not establish multiple customer charges/);
    assert.match(html, /Independent financial evidence, including bank\/settlement records, may still be missing/);
  }
});
