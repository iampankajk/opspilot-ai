"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createInvestigation, loadIncident, loadWorkspace, type IncidentEntry, type ThreadKind, type Workspace } from "../lib/investigations";

import ThreadCases from "./case-list";
import WorkspaceShell, { IncidentHeader, type WorkspaceView } from "./workspace-shell";

export default function InvestigationPanel() {
  const [reference, setReference] = useState("INC-2026-1042");
  const [entry, setEntry] = useState<IncidentEntry | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [selected, setSelected] = useState<ThreadKind>("payment_failures");
  const [view, setView] = useState<WorkspaceView>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(new Set<AbortController>());

  function showWorkspace(result: Workspace) {
    if (result.investigation_id !== workspace?.investigation_id || result.state_id !== workspace?.state_id) {
      setSelected("payment_failures"); setView("overview");
    }
    setWorkspace(result);
    const url = new URL(window.location.href);
    url.searchParams.set("investigation", result.investigation_id);
    window.history.replaceState(null, "", url);
  }

  async function run<T,>(operation: (signal: AbortSignal) => Promise<T>, success: (value: T) => void) {
    const controller = new AbortController();
    pending.current.add(controller);
    setBusy(true); setError(null);
    try {
      const result = await operation(controller.signal);
      if (!controller.signal.aborted) success(result);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Unable to load workspace. Retry the request.");
    } finally {
      pending.current.delete(controller);
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  useEffect(() => {
    const investigation = new URL(window.location.href).searchParams.get("investigation");
    if (investigation) void run(signal => loadWorkspace(investigation, signal), showWorkspace);
    const requests = pending.current;
    return () => { requests.forEach(controller => controller.abort()); requests.clear(); };
  }, []);

  const updateVersion = useCallback((version: number) => {
    setWorkspace(current => current && version > current.draft_version ? { ...current, draft_version: version } : current);
  }, []);

  return (
    <div className="investigation-panel">
      <details className={`entry-panel ${workspace ? "entry-panel-compact" : ""}`} open={!workspace}>
        <summary id="investigate-heading">{workspace ? "Open another incident" : "Open an investigation"}</summary>
        <div className="entry-content">
          <p>Start or resume your <a href="#demo-session" onClick={() => {
            const details = document.querySelector<HTMLDetailsElement>(".session-disclosure");
            if (details) { details.open = true; details.querySelector("summary")?.focus(); }
          }}>demo session</a>, then load a known incident. Your investigation is independent of other visitors.</p>
          <form onSubmit={event => {
            event.preventDefault();
            void run(signal => loadIncident(reference.trim(), signal), result => {
              setEntry(result); setWorkspace(null);
              const url = new URL(window.location.href); url.searchParams.delete("investigation");
              window.history.replaceState(null, "", url);
            });
          }}>
            <label htmlFor="incident-reference">Incident reference</label>
            <input id="incident-reference" value={reference} onChange={event => setReference(event.target.value)}
              required maxLength={128} disabled={busy} />
            <button type="submit" disabled={busy}>Load incident</button>
          </form>
          {entry && !workspace && <IncidentHeader {...entry} />}
          {entry && !workspace && <button disabled={busy} onClick={() => {
            void run(signal => createInvestigation(entry.incident.incident_id, signal), showWorkspace);
          }}>Create or resume investigation</button>}
        </div>
      </details>
      {busy && <p role="status">Loading workspace…</p>}
      {error && <p role="alert" className="failure">{error}</p>}
      {workspace && <>
        <WorkspaceShell workspace={workspace} thread={selected} view={view}
          onThread={thread => { if (thread !== selected) { setSelected(thread); setView("overview"); } }} onView={setView}>
          <ThreadCases key={`${workspace.investigation_id}:${workspace.state_id}:${selected}`} workspace={workspace} thread={selected} onVersion={updateVersion} />
        </WorkspaceShell>
        <details className="technical-details workspace-details">
          <summary>Workspace details</summary>
          <p className="request-id">Investigation: <code>{workspace.investigation_id}</code></p>
          <p className="request-id">State: <code>{workspace.state_id}</code> · Draft version {workspace.draft_version}</p>
          <button disabled={busy} onClick={() => void run(signal => loadWorkspace(workspace.investigation_id, signal), showWorkspace)}>
            Reload saved workspace
          </button>
        </details>
      </>}
    </div>
  );
}
