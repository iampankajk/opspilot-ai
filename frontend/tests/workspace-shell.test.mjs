import assert from "node:assert/strict";
import { test, mock } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Use the repository's existing React/TypeScript rendering test pattern.
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../app/workspace-shell.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext,
} }).outputText.replace('"react/jsx-runtime"', JSON.stringify(pathToFileURL(require.resolve("react/jsx-runtime")).href));
const { default: WorkspaceShell, IncidentHeader } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const workspace = {
  incident: { incident_ref: "INC-TEST", title: "Payment incident", severity: "SEV-2", region: "APAC", category: "Payments",
    description: "Source-supplied description", incident_time: { raw: "10:30 AM SGT", timezone: "Asia/Singapore" } },
  dataset_version: { version_label: "pinned-test-v1" },
  threads: [{ thread_kind: "payment_failures", label: "Payment failures", case_count: 2 },
    { thread_kind: "possible_duplicates", label: "Possible duplicates", case_count: 1 }],
};
const props = { workspace, thread: "payment_failures", view: "overview", onThread() {}, onView() {},
  children: createElement("div", { id: "existing-flow" }, "Existing case flow") };
const render = changes => renderToStaticMarkup(createElement(WorkspaceShell, { ...props, ...changes }));
function elements(node, found = []) {
  if (Array.isArray(node)) node.forEach(child => elements(child, found));
  else if (node?.props) { found.push(node); elements(node.props.children, found); }
  return found;
}

test("shell exposes both threads, configured counts, active Overview and no selected case", () => {
  const html = render();
  assert.match(html, /aria-label="Investigation threads"/);
  assert.match(html, /aria-pressed="true"[^>]*><span>Payment failures/);
  assert.match(html, /aria-pressed="false"[^>]*><span>Possible duplicates/);
  assert.match(html, /2 configured cases/);
  assert.match(html, /aria-current="page">Overview/);
  assert.match(html, /No active case/);
  assert.match(html, /id="existing-flow"/);
});

test("Evidence boundary offers Overview and keeps the existing flow mounted but hidden", () => {
  const tree = WorkspaceShell({ ...props, view: "evidence" });
  const nodes = elements(tree);
  const existing = nodes.find(node => node.props.hidden === true);
  assert.equal(existing.props.hidden, true);
  const html = render({ view: "evidence" });
  assert.match(html, /Select a case/);
  assert.match(html, /Go to Overview/);
  assert.match(html, /aria-current="page">Evidence/);
  const onView = mock.fn();
  const focus = mock.fn();
  const action = elements(WorkspaceShell({ ...props, view: "evidence", onView }))
    .find(node => node.type === "button" && node.props.children === "Go to Overview");
  action.props.onClick({ currentTarget: { closest: () => ({ querySelector: () => ({ focus }) }) } });
  assert.deepEqual(onView.mock.calls[0].arguments, ["overview"]);
  assert.equal(focus.mock.callCount(), 1);
});

test("thread and view actions only call navigation callbacks; Findings cannot activate", () => {
  const onThread = mock.fn(), onView = mock.fn();
  const fetch = mock.method(globalThis, "fetch", () => { throw new Error("Navigation must not fetch"); });
  try {
    const nodes = elements(WorkspaceShell({ ...props, onThread, onView }));
    const threads = nodes.find(node => node.props["aria-label"] === "Investigation threads");
    const threadButtons = elements(threads).filter(node => node.type === "button");
    threadButtons.forEach(node => node.props.onClick());
    assert.deepEqual(onThread.mock.calls.map(call => call.arguments[0]), ["payment_failures", "possible_duplicates"]);
    const views = nodes.find(node => node.props["aria-label"] === "Workspace views");
    const buttons = elements(views).filter(node => node.type === "button");
    buttons.filter(node => !node.props.disabled).forEach(node => node.props.onClick());
    assert.deepEqual(onView.mock.calls.map(call => call.arguments[0]), ["overview", "evidence"]);
    assert.equal(buttons[2].props.disabled, true);
    assert.equal(buttons[2].props.onClick, undefined);
    assert.equal(fetch.mock.callCount(), 0);
    assert.match(render(), /Findings <span>Unavailable/);
  } finally { fetch.mock.restore(); }
});

test("incident header preserves supplied timezone, raw time, description and pinned version", () => {
  const html = renderToStaticMarkup(createElement(IncidentHeader, workspace));
  for (const text of ["INC-TEST", "SEV-2", "APAC", "Payments", "10:30 AM SGT", "Asia/Singapore",
    "Source-supplied description", "Synthetic Data", "pinned-test-v1"]) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /10:30:00|UTC\+|confirmed|resolved/);
});

test("missing incident metadata is explicit, and source text is escaped", () => {
  const incident = { ...workspace.incident, severity: null, region: null, category: null, description: null,
    title: "<script>untrusted</script>", incident_time: { raw: null, timezone: null } };
  const html = renderToStaticMarkup(createElement(IncidentHeader, { ...workspace, incident }));
  for (const text of ["Severity not supplied", "Region not supplied", "Category not supplied", "Incident time not supplied", "Timezone not supplied"]) assert.ok(html.includes(text));
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>|Source-supplied description/);
});

test("shell measures header changes and disconnects its observer when unmounted", () => {
  let height = 148, resize, observed, disconnected = false;
  const original = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class {
    constructor(callback) { resize = callback; }
    observe(target) { observed = target; }
    disconnect() { disconnected = true; }
  };
  try {
    const setProperty = mock.fn();
    const header = { getBoundingClientRect: () => ({ height }) };
    const shell = { querySelector: () => header, style: { setProperty } };
    const cleanup = WorkspaceShell(props).props.ref(shell);
    assert.equal(observed, header);
    assert.deepEqual(setProperty.mock.calls.at(-1).arguments, ["--incident-header-height", "148px"]);
    height = 276.5; resize();
    assert.deepEqual(setProperty.mock.calls.at(-1).arguments, ["--incident-header-height", "276.5px"]);
    cleanup();
    assert.equal(disconnected, true);
  } finally {
    if (original === undefined) delete globalThis.ResizeObserver;
    else globalThis.ResizeObserver = original;
  }
});
