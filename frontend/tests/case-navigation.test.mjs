import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import ts from "typescript";
import * as api from "../lib/investigations.ts";
import * as navigation from "../lib/workspace-navigation.ts";
import * as jsxRuntime from "react/jsx-runtime";
const { jsx } = jsxRuntime;
import { renderToStaticMarkup } from "react-dom/server";

// Execute the real component handlers/effects with deterministic hook scheduling.
// Native DOM retention, focus and history traversal are checked separately in Chrome.
function component(name, imports = {}, hooks = {}) {
  const source = readFileSync(new URL(`../app/${name}.tsx`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
  const module = { exports: {} };
  const require = id => {
    if (id === "react") return hooks;
    if (id === "react/jsx-runtime") return jsxRuntime;
    if (id.includes("workspace-navigation")) return navigation;
    if (id.includes("lib/investigations")) return { ...api, ...imports.api };
    if (id.includes("lib/evidence")) return imports.evidence;
    if (id === "./case-list") return { __esModule: true, default: "CaseList", CaseContext: "CaseContext" };
    if (id === "./evidence-view") return { EvidenceView: "EvidenceView" };
    return { __esModule: true, default: id.slice(2) };
  };
  new Function("require", "module", "exports", code)(require, module, module.exports);
  return module.exports;
}
function mount(name, props, imports = {}) {
  const slots = [], effects = [];
  let cursor = 0;
  const hooks = {
    useState(initial) { const i = cursor++; slots[i] ??= { value: typeof initial === "function" ? initial() : initial };
      return [slots[i].value, update => { slots[i].value = typeof update === "function" ? update(slots[i].value) : update; }]; },
    useRef(value) { const i = cursor++; return slots[i] ??= { current: value }; },
    useEffect(callback, deps) { const i = cursor++, previous = slots[i];
      if (!previous || deps.some((d, j) => d !== previous.deps[j])) {
        slots[i] = { deps, cleanup: previous?.cleanup }; effects.push(() => { slots[i].cleanup?.(); slots[i].cleanup = callback(); });
      } },
    useCallback(callback) { cursor++; return callback; },
    useLayoutEffect() { cursor++; }, // DOM geometry is exercised by the browser walkthrough.
  };
  const Component = component(name, imports, hooks).default;
  return { render() { cursor = 0; const tree = Component(props); effects.splice(0).forEach(run => run()); return tree; },
    unmount() { slots.forEach(slot => slot?.cleanup?.()); } };
}
const settle = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const c = { case_id: "a", case_reference: "CASE-A", primary_report_record_id: "report-a", customer_ref: "CUST-A",
  reported_order_ref: null, related_order_refs: [{ value: "candidate-order", association: "candidate", basis_record_id: "lookup-a" }],
  reported_issue: "Reported failure <script>", reported_money: { currency: "SGD", amount: "120.00" },
  payment_state: null, investigation_progress: "not_started", reported_at: { raw: "10:33 SGT", timezone: "Asia/Singapore" } };
const workspace = { investigation_id: "investigation", state_id: "state", draft_version: 1,
  dataset_version: { dataset_version_id: "dataset", fixture_digest: "digest" } };

test("scope invalidation ignores draft counters but fences investigation/state/dataset and auth loss", () => {
  const scope = navigation.workspaceScope(workspace);
  assert.equal(navigation.workspaceScope({ ...workspace, draft_version: 9 }), scope);
  for (const change of [{ investigation_id: "other" }, { state_id: "other" },
    { dataset_version: { ...workspace.dataset_version, fixture_digest: "other" } }])
    assert.notEqual(navigation.workspaceScope({ ...workspace, ...change }), scope);
  for (const [status, code] of [[401, "SESSION_EXPIRED"], [403, "FORBIDDEN"], [409, "STALE_STATE"], [404, "NOT_FOUND"]])
    assert.ok(navigation.invalidatesContext(new api.InvestigationAPIError(status, code)));
  assert.equal(navigation.invalidatesContext(new api.InvestigationAPIError(409, "STALE_DRAFT_VERSION")), false);
  assert.equal(navigation.readLocation({ scope: "other", location: navigation.initialLocation }, scope), null);
});

test("compact Overview uses one native row action, exact reported money and separate candidate basis", () => {
  const { default: CaseList, CaseContext } = component("case-list");
  const html = renderToStaticMarkup(jsx(CaseList, { result: { status: "ready", cases: [c] }, selectedCaseId: null, onSelect() {} }));
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  for (const text of ["Open Evidence for CASE-A", "SGD 120.00", "Reported order: Not supplied in the report",
    "Related order (candidate): candidate-order", "lookup-a", "Not started", "Not established at case level"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /<script>|Inspect evidence|confirmed charge|In progress|Reviewed/);
  const context = renderToStaticMarkup(jsx(CaseContext, { selectedCase: c, contextId: "selected-context" }));
  assert.match(context, /id="selected-context" tabindex="-1"/);
  assert.match(context, /Report created: 10:33 SGT/);
});

test("loading, empty and failed case lists remain distinct and retry is explicit", () => {
  const { default: CaseList } = component("case-list");
  const render = result => renderToStaticMarkup(jsx(CaseList, { result, selectedCaseId: null, onSelect() {}, onRetry() {} }));
  assert.match(render({ status: "loading" }), /Loading cases/);
  assert.match(render({ status: "ready", cases: [] }), /No cases in this thread/);
  const failed = render({ status: "failed", message: "Unable to load cases" });
  assert.match(failed, /role="alert"/); assert.match(failed, /Retry cases/); assert.doesNotMatch(failed, /No cases/);
});

test("real navigation handlers retain independent thread views/cases with no evidence operations", async t => {
  const original = globalThis.window;
  globalThis.window = { scrollY: 180, location: { href: "https://localhost/?investigation=investigation" },
    history: { state: {}, replaceState(state) { this.state = state; }, pushState(state) { this.state = state; } },
    addEventListener() {}, removeEventListener() {} };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  let loads = 0;
  const h = mount("case-workspace", { workspace: { ...workspace, threads: [
    { thread_kind: "payment_failures", label: "Payment failures" }, { thread_kind: "possible_duplicates", label: "Possible duplicates" }] },
    onVersion() {}, onScopeError(e) { throw e; } }, { api: { async loadCases(_i, _s, thread) { loads++; return { draft_version: 1, cases: [{ ...c, case_id: thread }] }; } } });
  h.render(); await settle();
  let tree = h.render(); assert.equal(tree.props.hasSelectedCase, false);
  tree.props.children[0].props.children.props.onSelect("payment_failures");
  tree = h.render(); assert.equal(tree.props.view, "evidence"); assert.equal(tree.props.hasSelectedCase, true);
  tree.props.onThread("possible_duplicates"); h.render(); await settle(); tree = h.render();
  assert.equal(tree.props.view, "overview"); assert.equal(tree.props.hasSelectedCase, false);
  tree.props.children[1].props.children.props.onSelect("possible_duplicates"); tree = h.render();
  tree.props.onThread("payment_failures"); tree = h.render();
  assert.equal(tree.props.view, "evidence"); assert.equal(tree.props.thread, "payment_failures");
  assert.equal(tree.props.evidence.flat().filter(Boolean).length, 2);
  assert.equal(loads, 2); // Revisiting uses page memory, not another cases GET or evidence POST.
  h.unmount();
});

function evidenceHarness(overrides = {}, selectedCase = c) {
  let posts = 0, invalidated = [], versions = [];
  const reply = deferred();
  const h = mount("evidence-panel", { workspace, thread: "payment_failures", selectedCase,
    onVersion: value => versions.push(value), onScopeError: error => invalidated.push(error) },
  { api: { loadWorkspace: async () => workspace, ...overrides }, evidence: { inspectEvidence() { posts++; return reply.promise; } } });
  return { h, reply, invalidated, versions, get posts() { return posts; } };
}

test("late result stays with its originating case and unmounted scope ignores it", async () => {
  const a = evidenceHarness(), b = evidenceHarness({}, { ...c, case_id: "b", case_reference: "CASE-B" });
  a.h.render().props.onInspect(); await settle();
  assert.equal(a.posts, 1); assert.equal(b.h.render().props.result.status, "idle"); assert.equal(b.posts, 0);
  a.reply.resolve({ draft_version: 2, evidence_request_id: "request-a", status: "completed" }); await settle();
  assert.equal(a.h.render().props.result.data.evidence_request_id, "request-a");
  assert.equal(b.h.render().props.result.status, "idle");
  const abandoned = evidenceHarness(); abandoned.h.render().props.onInspect(); await settle(); abandoned.h.unmount();
  abandoned.reply.resolve({ draft_version: 2, evidence_request_id: "late", status: "completed" }); await settle();
  assert.equal(abandoned.h.render().props.result.status, "loading"); assert.deepEqual(abandoned.versions, [1]);
  a.h.unmount(); b.h.unmount();
});

test("preflight changed scope or expired authorization invalidates cache without evidence POST", async () => {
  for (const loadWorkspace of [async () => ({ ...workspace, state_id: "replacement" }), async () => {
    throw new api.InvestigationAPIError(401, "SESSION_EXPIRED"); }]) {
    const instance = evidenceHarness({ loadWorkspace }); instance.h.render().props.onInspect(); await settle();
    assert.equal(instance.posts, 0); assert.equal(instance.invalidated.length, 1); instance.h.unmount();
  }
});

test("stale version reconciles current workspace without automatic POST retry", async () => {
  const instance = evidenceHarness(); instance.h.render().props.onInspect(); await settle();
  instance.reply.reject(new api.InvestigationAPIError(409, "STALE_DRAFT_VERSION", { state_id: "state", draft_version: 4 }));
  await settle();
  assert.equal(instance.posts, 1); assert.equal(instance.invalidated.length, 0);
  assert.deepEqual(instance.versions, [1, 4, 1]); assert.equal(instance.h.render().props.result.status, "failed");
  instance.h.unmount();
});

test("rapid repeat activation produces one operation; partial retry belongs only to that case", async () => {
  const a = evidenceHarness(), b = evidenceHarness({}, { ...c, case_id: "b" });
  const initial = a.h.render(); initial.props.onInspect(); initial.props.onInspect(); await settle();
  assert.equal(a.posts, 1);
  a.reply.resolve({ draft_version: 2, evidence_request_id: "partial-a", status: "partial" }); await settle();
  const ready = a.h.render();
  assert.equal(ready.props.retry, "partial-a"); assert.deepEqual(ready.props.history, ["partial-a"]);
  assert.equal(b.h.render().props.retry, undefined); assert.deepEqual(b.h.render().props.history, []);
  a.h.unmount(); b.h.unmount();
});

test("a stale response naming another state invalidates before retaining its request reference", async () => {
  const instance = evidenceHarness(); instance.h.render().props.onInspect(); await settle();
  instance.reply.reject(new api.InvestigationAPIError(409, "STALE_DRAFT_VERSION", {
    state_id: "other-state", evidence_request_id: "foreign-request", draft_version: 5 })); await settle();
  assert.equal(instance.invalidated.length, 1); assert.equal(instance.h.render().props.retry, undefined);
  assert.deepEqual(instance.h.render().props.history, []); instance.h.unmount();
});

function elements(node, found = []) {
  if (Array.isArray(node)) node.forEach(child => elements(child, found));
  else if (node?.props) { found.push(node); elements(node.props.children, found); }
  return found;
}

test("same-thread cases retain separate mounted panels and selection never inspects evidence", async t => {
  const original = globalThis.window;
  globalThis.window = { scrollY: 0, location: { href: "https://localhost/?investigation=investigation" },
    history: { state: {}, replaceState(state) { this.state = state; }, pushState(state) { this.state = state; } },
    addEventListener() {}, removeEventListener() {} };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  const h = mount("case-workspace", { workspace: { ...workspace, threads: [{ thread_kind: "payment_failures", label: "Payment failures" }] },
    onVersion() {}, onScopeError(e) { throw e; } }, { api: { async loadCases() {
    return { draft_version: 1, cases: [c, { ...c, case_id: "b", case_reference: "CASE-B" }] };
  } } });
  h.render(); await settle();
  let tree = h.render(); tree.props.children[0].props.children.props.onSelect("a");
  tree = h.render(); tree.props.children[0].props.children.props.onSelect("b"); tree = h.render();
  const panels = tree.props.evidence.flat().filter(Boolean);
  assert.equal(panels.length, 2); assert.deepEqual(panels.map(n => n.props.hidden), [true, false]);
  assert.deepEqual(panels.map(n => n.props.children[2].props.selectedCase.case_id), ["a", "b"]);
  tree.props.children[0].props.children.props.onSelect("a"); tree = h.render();
  assert.deepEqual(tree.props.evidence.flat().filter(Boolean).map(n => n.props.hidden), [false, true]);
  h.unmount();
});

test("scope invalidation removes every protected panel and a late version callback cannot reopen it", async t => {
  const original = globalThis.window;
  globalThis.window = { location: { href: "https://localhost/?investigation=investigation" }, history: { state: {}, replaceState() {} } };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  for (const error of [new api.InvestigationAPIError(409, "STALE_STATE"), new api.InvestigationAPIError(401, "SESSION_EXPIRED")]) {
    let gets = 0;
    const h = mount("investigation-panel", {}, { api: { async loadWorkspace() { gets++; return workspace; } } });
    h.render(); await settle();
    const active = elements(h.render()).find(n => n.type === "case-workspace");
    assert.ok(active); active.props.onScopeError(error);
    assert.equal(elements(h.render()).some(n => n.type === "case-workspace"), false);
    active.props.onVersion(9);
    const invalid = elements(h.render());
    assert.equal(invalid.some(n => n.type === "case-workspace"), false);
    assert.ok(invalid.some(n => n.props.role === "alert" && n.props.children === error.message));
    assert.equal(gets, 1); // No automatic workspace retry or replacement visitor.
    if (error.code === "STALE_STATE") assert.ok(invalid.some(n => n.type === "button" && n.props.children.trim() === "Reload saved workspace"));
    h.unmount();
  }
});

test("missing unrelated incident preserves valid local context; missing owned workspace clears it", async t => {
  const original = globalThis.window;
  globalThis.window = { location: { href: "https://localhost/?investigation=investigation" }, history: { state: {}, replaceState() {} } };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  let gets = 0;
  const h = mount("investigation-panel", {}, { api: {
    async loadWorkspace() { if (++gets === 1) return workspace; throw new api.InvestigationAPIError(404, "NOT_FOUND"); },
    async loadIncident() { throw new api.InvestigationAPIError(404, "NOT_FOUND"); },
  } });
  h.render(); await settle();
  const before = elements(h.render()).find(n => n.type === "case-workspace");
  elements(h.render()).find(n => n.type === "form").props.onSubmit({ preventDefault() {} }); await settle();
  const after = elements(h.render()).find(n => n.type === "case-workspace");
  assert.ok(after); assert.equal(after.key, before.key);
  elements(h.render()).find(n => n.type === "button" && n.props.children.trim() === "Reload saved workspace").props.onClick(); await settle();
  assert.equal(elements(h.render()).some(n => n.type === "case-workspace"), false);
  h.unmount();
});

test("delayed workspace GET cannot restore context after inspection invalidates its generation", async t => {
  const original = globalThis.window;
  globalThis.window = { location: { href: "https://localhost/?investigation=investigation" }, history: { state: {}, replaceState() {} } };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  // Exercise both normal cancellation and a transport whose cancellation is ineffective.
  for (const ineffectiveAbort of [false, true]) {
    const abort = ineffectiveAbort ? t.mock.method(AbortController.prototype, "abort", () => {}) : null;
    const delayed = deferred();
    let gets = 0, signal;
    const h = mount("investigation-panel", {}, { api: { async loadWorkspace(_id, requestSignal) {
      if (++gets === 1) return workspace;
      if (gets === 2) { signal = requestSignal; return delayed.promise; }
      return { ...workspace, state_id: "recovered-state" };
    } } });
    h.render(); await settle();
    let tree = h.render();
    const active = elements(tree).find(n => n.type === "case-workspace");
    elements(tree).find(n => n.type === "button" && n.props.children.trim() === "Reload saved workspace").props.onClick();
    active.props.onScopeError(new api.InvestigationAPIError(409, "STALE_STATE"));
    tree = h.render();
    assert.equal(elements(tree).some(n => n.type === "case-workspace"), false);
    if (!ineffectiveAbort) assert.equal(signal.aborted, true);
    const recovery = elements(tree).find(n => n.type === "button" && n.props.children.trim() === "Reload saved workspace");
    assert.equal(recovery.props.disabled, false); // Invalidation releases busy state.
    recovery.props.onClick(); await settle();
    assert.equal(elements(h.render()).find(n => n.type === "case-workspace").props.workspace.state_id, "recovered-state");
    delayed.resolve(workspace); await settle();
    assert.equal(elements(h.render()).find(n => n.type === "case-workspace").props.workspace.state_id, "recovered-state");
    h.unmount(); abort?.mock.restore();
  }
});

test("late successful reload stays rejected after SESSION_EXPIRED and explicit resume still works", async t => {
  const original = globalThis.window;
  globalThis.window = { location: { href: "https://localhost/?investigation=investigation" }, history: { state: {}, replaceState() {} } };
  t.after(() => { if (original === undefined) delete globalThis.window; else globalThis.window = original; });
  const delayed = deferred(); let gets = 0, signal;
  const h = mount("investigation-panel", {}, { api: {
    async loadWorkspace(_id, requestSignal) { if (++gets === 1) return workspace; signal = requestSignal; return delayed.promise; },
    async loadIncident() { return { incident: { incident_id: "incident" }, dataset_version: workspace.dataset_version }; },
    async createInvestigation() { return { ...workspace, investigation_id: "new-owned-workspace" }; },
  } });
  h.render(); await settle();
  let nodes = elements(h.render());
  const active = nodes.find(n => n.type === "case-workspace");
  nodes.find(n => n.type === "button" && n.props.children.trim() === "Reload saved workspace").props.onClick();
  active.props.onScopeError(new api.InvestigationAPIError(401, "SESSION_EXPIRED"));
  assert.equal(signal.aborted, true);
  delayed.resolve(workspace); await settle();
  nodes = elements(h.render());
  assert.equal(nodes.some(n => n.type === "case-workspace"), false);
  assert.ok(nodes.some(n => n.props.role === "alert" && /expired/.test(n.props.children)));
  assert.equal(gets, 2); // No case-loading restart or automatic recovery operation.
  // After a legitimate explicit session recovery, the entry/resume path is usable.
  nodes.find(n => n.type === "form").props.onSubmit({ preventDefault() {} }); await settle();
  nodes = elements(h.render());
  nodes.find(n => n.type === "button" && n.props.children.trim() === "Create or resume investigation").props.onClick(); await settle();
  assert.equal(elements(h.render()).find(n => n.type === "case-workspace").props.workspace.investigation_id, "new-owned-workspace");
  h.unmount();
});

function focusFixture(t) {
  const previousWindow = globalThis.window, previousDocument = globalThis.document;
  globalThis.window = { innerWidth: 1440, innerHeight: 900, scrollY: 2125.5 };
  globalThis.document = { activeElement: null, querySelector: () => ({ getBoundingClientRect: () => ({ bottom: 146 }) }) };
  t.after(() => {
    if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow;
    if (previousDocument === undefined) delete globalThis.document; else globalThis.document = previousDocument;
  });
  function node({ top = 250, height = 32, native = true, connected = true, hidden = false, closed = false, keyboard = true } = {}) {
    const attributes = new Map(), events = new Map(), calls = [];
    return { isConnected: connected, tabIndex: native ? 0 : -1, attributes, events, calls,
      closest(selector) { return selector === '[hidden]' ? hidden ? {} : null : closed ? { querySelector: () => ({ contains: () => false }) } : null; },
      matches: () => keyboard, getClientRects: () => [{}],
      getBoundingClientRect: () => ({ top, bottom: top + height, left: 330, right: 1200, width: 870, height }),
      hasAttribute: name => attributes.has(name), setAttribute(name, value) { attributes.set(name, value); },
      removeAttribute(name) { attributes.delete(name); },
      addEventListener(name, callback) { events.set(name, callback); },
      focus(options) { calls.push(options); document.activeElement = this; },
    };
  }
  const trigger = node({ top: -1705 }); document.activeElement = trigger;
  return { node, trigger, panel: (controls, content = []) => ({ querySelectorAll: selector => selector.startsWith('summary') ? controls : content }) };
}

test("retained Evidence keyboard return focuses a live visible control without moving scroll", t => {
  const { focusRetainedEvidence } = component('case-workspace');
  const { node, trigger, panel } = focusFixture(t);
  const removed = node({ connected: false }), hidden = node({ hidden: true }), closed = node({ closed: true });
  const obscured = node({ top: 130 }), visible = node();
  assert.equal(focusRetainedEvidence(panel([removed, hidden, closed, obscured, visible]), trigger), visible);
  assert.deepEqual(visible.calls, [{ preventScroll: true }]);
  assert.ok([removed, hidden, closed, obscured].every(n => n.calls.length === 0));
  assert.equal(window.scrollY, 2125.5);
});

test("missing record focus destination falls back to live text with a temporary tab index", t => {
  const { focusRetainedEvidence } = component('case-workspace');
  const { node, trigger, panel } = focusFixture(t);
  const removed = node({ connected: false }), paragraph = node({ native: false });
  assert.equal(focusRetainedEvidence(panel([removed], [paragraph]), trigger), paragraph);
  assert.equal(paragraph.attributes.get('tabindex'), '-1');
  assert.deepEqual(paragraph.calls, [{ preventScroll: true }]);
  paragraph.events.get('blur')(); assert.equal(paragraph.attributes.has('tabindex'), false);
  assert.equal(window.scrollY, 2125.5);
});

test("retained Evidence repair leaves pointer, newer focus, and onscreen tab focus alone", t => {
  const { focusRetainedEvidence } = component('case-workspace');
  const { node, trigger, panel } = focusFixture(t), destination = node();
  document.activeElement = node(); assert.equal(focusRetainedEvidence(panel([destination]), trigger), null);
  const pointer = node({ top: -1705, keyboard: false }); document.activeElement = pointer;
  assert.equal(focusRetainedEvidence(panel([destination]), pointer), null);
  const onscreen = node(); document.activeElement = onscreen;
  assert.equal(focusRetainedEvidence(panel([destination]), onscreen), null);
  assert.deepEqual(destination.calls, []);
});

test("long visible Evidence content remains a non-scrolling focus fallback", t => {
  const { focusRetainedEvidence } = component('case-workspace');
  const { node, trigger, panel } = focusFixture(t), payload = node({ top: 160, height: 1200, native: false });
  assert.equal(focusRetainedEvidence(panel([], [payload]), trigger), payload);
  assert.deepEqual(payload.calls, [{ preventScroll: true }]); assert.equal(window.scrollY, 2125.5);
});
