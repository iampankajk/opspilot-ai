"use client";

import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { loadCases, type ThreadKind, type Workspace } from "../lib/investigations";
import { revealEvidenceRecord } from "../lib/evidence.ts";
import { initialLocation, invalidatesContext, locationKey, readLocation, workspaceScope, type CaseLocation } from "../lib/workspace-navigation";
import CaseList, { CaseContext, type CaseListResult } from "./case-list";
import EvidencePanel from "./evidence-panel";
import WorkspaceShell from "./workspace-shell";

const threads: ThreadKind[] = ["payment_failures", "possible_duplicates"];
const contextId = (thread: ThreadKind, caseId: string) => `case-${thread}-${caseId}`;

function visibleFocusTarget(node: HTMLElement, headerBottom: number, fully = true) {
  if (!node.isConnected || node.closest("[hidden]") || !node.getClientRects().length) return false;
  // Closed details may retain descendant geometry in the browser. A summary
  // inside another closed record is still hidden, even if its own details exist.
  for (let closed = node.closest("details:not([open])"); closed; closed = closed.parentElement?.closest("details:not([open])") ?? null) {
    if (!closed.querySelector(":scope > summary")?.contains(node)) return false;
  }
  const rect = node.getBoundingClientRect();
  const top = Math.max(0, headerBottom) + 8, bottom = window.innerHeight - 8;
  return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.left < window.innerWidth &&
    (fully ? rect.top >= top && rect.bottom <= bottom : rect.bottom > top && rect.top < bottom);
}

export function focusRetainedEvidence(panel: HTMLElement, trigger: HTMLElement) {
  // A later user action must win over this deferred keyboard return.
  if (document.activeElement !== trigger || !trigger.matches(".workspace-tabs button:focus-visible")) return null;
  const headerBottom = document.querySelector(".workspace-shell > .incident-header")?.getBoundingClientRect().bottom ?? 0;
  if (visibleFocusTarget(trigger, headerBottom)) return null;
  // Resolve from live content, so removed/replaced records never leave a stale
  // focus handle. Prefer an existing control, then readable content at this position.
  const controls = Array.from(panel.querySelectorAll<HTMLElement>("summary, button:not(:disabled), a[href]"));
  const content = Array.from(panel.querySelectorAll<HTMLElement>("h4, h5, h6, p, pre"));
  const candidates = [...controls, ...content].filter(node => visibleFocusTarget(node, headerBottom));
  candidates.push(...content.filter(node => visibleFocusTarget(node, headerBottom, false)));
  for (const destination of candidates) {
    const temporary = !destination.hasAttribute("tabindex") && destination.tabIndex < 0;
    if (temporary) destination.setAttribute("tabindex", "-1");
    destination.focus({ preventScroll: true });
    if (document.activeElement === destination) {
      if (temporary) destination.addEventListener("blur", () => destination.removeAttribute("tabindex"), { once: true });
      return destination;
    }
    if (temporary) destination.removeAttribute("tabindex");
  }
  return null;
}

export default function CaseWorkspace({ workspace, onVersion, onScopeError }: {
  workspace: Workspace; onVersion: (version: number) => void;
  onScopeError: (error: unknown) => void;
}) {
  const scope = workspaceScope(workspace);
  // History entries can replay only within this mounted page, never after reload
  // or an invalidation/remount that discarded its case/result memory.
  const [historyScope] = useState(() => `${scope}:${crypto.randomUUID()}`);
  const [location, setLocation] = useState<CaseLocation>(initialLocation);
  const [lists, setLists] = useState<Partial<Record<ThreadKind, CaseListResult>>>({});
  const [visited, setVisited] = useState<string[]>([]);
  const remembered = useRef<Record<ThreadKind, CaseLocation>>({ payment_failures: initialLocation,
    possible_duplicates: { thread: "possible_duplicates", view: "overview", caseId: null } });
  const current = useRef(location);
  // Scroll positions have one authority: page memory, keyed by our history entry ID.
  // The per-location index only identifies the most recently visited entry.
  const positions = useRef(new Map<string, number>());
  const latestEntry = useRef(new Map<string, string>());
  const entryId = useRef(crypto.randomUUID());
  const restoration = useRef<{ y: number; focus: "case" | "history" | false; hash?: string; keyboardReturn?: HTMLElement } | null>(null);
  const pending = useRef(new Map<ThreadKind, AbortController>());
  const listRef = useRef(lists);
  listRef.current = lists;

  function savePosition() {
    if (!restoration.current) positions.current.set(entryId.current, window.scrollY);
  }
  function pushEntry(next: CaseLocation, url: URL, y: number) {
    const id = crypto.randomUUID();
    // Pass only application metadata. Next.js owns its router state and copies it
    // through its public History API integration, including for record fragments.
    window.history.pushState({ opspilot: { scope: historyScope, location: next, entryId: id } }, "", url);
    entryId.current = id;
    positions.current.set(id, y);
    latestEntry.current.set(locationKey(next), id);
  }
  function navigate(next: CaseLocation, focus = false, keyboardReturn?: HTMLElement) {
    if (JSON.stringify(next) === JSON.stringify(current.current)) {
      if (focus && next.caseId) {
        const heading = document.getElementById(contextId(next.thread, next.caseId));
        heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: "start" });
      }
      return;
    }
    savePosition();
    const previousEntry = latestEntry.current.get(locationKey(next));
    const y = previousEntry ? positions.current.get(previousEntry) ?? 0 : 0;
    const url = new URL(window.location.href); url.hash = "";
    pushEntry(next, url, y);
    restoration.current = { y, focus: focus ? "case" : false, keyboardReturn };
    remembered.current[next.thread] = next;
    current.current = next;
    setLocation(next);
  }

  function navigateRecord(event: MouseEvent<HTMLDivElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>('a[href^="#evidence-"]') : null;
    const panel = link?.closest(".evidence-panel");
    const target = Array.from(panel?.querySelectorAll<HTMLDetailsElement>("details[id]") ?? [])
      .find(record => `#${record.id}` === link?.getAttribute("href"));
    if (!target || !link) return;
    // The link's own handler already reveals the record and schedules summary
    // focus. Replace only the browser's default hash-history write, which would
    // otherwise lose the framework's router state.
    event.preventDefault();
    savePosition();
    const url = new URL(window.location.href); url.hash = target.id;
    if (url.href !== window.location.href) pushEntry(current.current, url, window.scrollY);
    target.scrollIntoView({ block: "start" });
    positions.current.set(entryId.current, window.scrollY);
  }

  useEffect(() => {
    const previousRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    positions.current.set(entryId.current, window.scrollY);
    latestEntry.current.set(locationKey(current.current), entryId.current);
    window.history.replaceState({ opspilot: { scope: historyScope, location: current.current, entryId: entryId.current } }, "");
    function pop(event: PopStateEvent) {
      const metadata = event.state?.opspilot;
      const next = readLocation(metadata, historyScope);
      if (!next || typeof metadata.entryId !== "string" || !positions.current.has(metadata.entryId)) return;
      const data = listRef.current[next.thread];
      if (next.caseId && (data?.status !== "ready" || !data.cases.some(c => c.case_id === next.caseId))) return;
      savePosition();
      const y = positions.current.get(metadata.entryId) ?? 0;
      entryId.current = metadata.entryId;
      latestEntry.current.set(locationKey(next), metadata.entryId);
      restoration.current = { y, focus: "history", hash: window.location.hash };
      remembered.current[next.thread] = next;
      current.current = next;
      // Fragment-only traversals also need restoration/focus, even in the same view.
      setLocation({ ...next });
    }
    const scroll = () => savePosition();
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("popstate", pop);
    const requests = pending.current;
    return () => {
      window.history.scrollRestoration = previousRestoration;
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("popstate", pop);
      requests.forEach(c => c.abort()); requests.clear();
    };
  }, [historyScope]);

  useLayoutEffect(() => {
    const target = restoration.current;
    if (!target) return;
    const frame = requestAnimationFrame(() => {
      if (target.focus === "case" && location.caseId) {
        const heading = document.getElementById(contextId(location.thread, location.caseId));
        heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: "start" });
      } else {
        const record = target.hash ? document.getElementById(target.hash.slice(1)) : null;
        if (record instanceof HTMLDetailsElement && record.closest('.evidence-panel')?.getBoundingClientRect().height) {
          revealEvidenceRecord(record);
          record.querySelector("summary")?.focus({ preventScroll: true });
        } else if (target.focus === "history") {
          const candidates = Array.from(document.querySelectorAll<HTMLElement>(
            '.case-nav [aria-current="true"], .workspace-tabs [aria-current="page"], #thread-heading'));
          window.scrollTo(0, target.y);
          const visible = candidates.find(node => { const rect = node.getBoundingClientRect();
            return rect.top >= 0 && rect.bottom <= window.innerHeight; });
          (visible ?? document.querySelector<HTMLElement>('.workspace-content'))?.focus({ preventScroll: true });
        }
        window.scrollTo(0, target.y);
        if (record instanceof HTMLDetailsElement && record.open && record.closest('.evidence-panel')?.getBoundingClientRect().height) {
          const summary = record.querySelector("summary");
          const bounds = summary?.getBoundingClientRect();
          const headerBottom = document.querySelector('.workspace-shell > .incident-header')?.getBoundingClientRect().bottom ?? 0;
          // A user may have scrolled away from a fragment before leaving. If
          // history focuses its target, keep that focus visible below the header.
          if (bounds && (bounds.top < Math.max(0, headerBottom) || bounds.bottom > window.innerHeight)) {
            summary?.scrollIntoView({ block: "start" });
          }
        }
      }
      if (target.keyboardReturn && location.view === "evidence" && location.caseId) {
        const context = document.getElementById(contextId(location.thread, location.caseId));
        const panel = context?.closest(".selected-case")?.parentElement?.querySelector<HTMLElement>(".evidence-panel");
        if (panel) focusRetainedEvidence(panel, target.keyboardReturn);
      }
      restoration.current = null;
      positions.current.set(entryId.current, window.scrollY);
    });
    return () => cancelAnimationFrame(frame);
  }, [location]);

  async function fetchCases(thread: ThreadKind) {
    if (pending.current.has(thread)) return;
    const controller = new AbortController(); pending.current.set(thread, controller);
    setLists(previous => ({ ...previous, [thread]: { status: "loading" } }));
    try {
      const data = await loadCases(workspace.investigation_id, workspace.state_id, thread, controller.signal);
      if (controller.signal.aborted) return;
      onVersion(data.draft_version);
      setLists(previous => ({ ...previous, [thread]: { status: "ready", cases: data.cases } }));
    } catch (error) {
      if (controller.signal.aborted) return;
      if (invalidatesContext(error)) { onScopeError(error); return; }
      setLists(previous => ({ ...previous, [thread]: { status: "failed", message: error instanceof Error ? error.message : "Unable to load cases." } }));
    } finally { if (pending.current.get(thread) === controller) pending.current.delete(thread); }
  }
  useEffect(() => {
    if (!listRef.current[location.thread]) void fetchCases(location.thread);
  }, [location.thread]);

  function selectCase(id: string) {
    const key = contextId(location.thread, id);
    setVisited(previous => previous.includes(key) ? previous : [...previous, key]);
    navigate({ ...location, view: "evidence", caseId: id }, true);
  }
  const result = lists[location.thread] ?? { status: "loading" };
  const navigation = <>
    {!location.caseId && <p className="muted">No active case</p>}
    {result.status === "loading" && <p>Loading cases…</p>}
    {result.status === "failed" && <p>Case list unavailable. Retry in Overview.</p>}
    {result.status === "ready" && <nav className="case-nav" aria-label={`${workspace.threads.find(t => t.thread_kind === location.thread)!.label} cases`}>
      {result.cases.length === 0 && <p>No configured cases.</p>}
      {result.cases.map(c => <button key={c.case_id} aria-current={location.caseId === c.case_id ? "true" : undefined}
        onClick={() => selectCase(c.case_id)}><strong>{c.case_reference}</strong><span>{c.customer_ref ?? "Customer not supplied"}</span></button>)}
    </nav>}
  </>;
  return <WorkspaceShell workspace={workspace} thread={location.thread} view={location.view}
    onThread={thread => navigate(remembered.current[thread])} onView={view => {
      const trigger = document.activeElement;
      const keyboardReturn = view === "evidence" && location.view === "overview" && location.caseId &&
        trigger instanceof HTMLElement && trigger.matches(".workspace-tabs button:focus-visible") ? trigger : undefined;
      navigate({ ...location, view }, false, keyboardReturn);
    }}
    caseNavigation={navigation} hasSelectedCase={location.caseId !== null}
    evidence={threads.map(thread => {
      const list = lists[thread];
      return list?.status === "ready" && list.cases.filter(c => visited.includes(contextId(thread, c.case_id))).map(c =>
        <div key={`${thread}:${c.case_id}`} onClick={navigateRecord} hidden={location.thread !== thread || location.caseId !== c.case_id}>
          <CaseContext selectedCase={c} contextId={contextId(thread, c.case_id)} />
          <EvidencePanel workspace={workspace} thread={thread} selectedCase={c} onVersion={onVersion}
            onScopeError={onScopeError} />
        </div>);
    })}>
    {threads.map(thread => <div key={thread} hidden={location.thread !== thread}>
      <CaseList result={lists[thread] ?? { status: "loading" }} selectedCaseId={remembered.current[thread].caseId}
        onSelect={selectCase} onRetry={() => void fetchCases(thread)} />
    </div>)}
  </WorkspaceShell>;
}
