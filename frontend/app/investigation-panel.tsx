"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createInvestigation, loadIncident, loadWorkspace, type IncidentEntry, type Workspace } from "../lib/investigations";
import { invalidatesContext, workspaceScope } from "../lib/workspace-navigation";

import CaseWorkspace from "./case-workspace";
import { IncidentHeader } from "./workspace-shell";

export default function InvestigationPanel() {
  const [reference, setReference] = useState("INC-2026-1042");
  const [entry, setEntry] = useState<IncidentEntry | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [validContext, setValidContext] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(new Set<AbortController>());
  const contextGeneration = useRef(0);

  function showWorkspace(result: Workspace) {
    setValidContext(true);
    setWorkspace(previous => previous && workspaceScope(previous) === workspaceScope(result)
      ? { ...result, draft_version: Math.max(previous.draft_version, result.draft_version) } : result);
    const url = new URL(window.location.href);
    url.searchParams.set("investigation", result.investigation_id);
    window.history.replaceState(window.history.state, "", url);
  }

  const invalidateContext = useCallback((failure: unknown) => {
    contextGeneration.current++;
    pending.current.forEach(controller => controller.abort());
    pending.current.clear();
    setBusy(false);
    setValidContext(false); // Unmount every protected local case/result and abort its client requests.
    setError(failure instanceof Error ? failure.message : "Reload the saved workspace before continuing.");
    if (invalidatesContext(failure) && failure.code !== "STALE_STATE") {
      setWorkspace(null); setEntry(null);
    }
  }, []);

  async function run<T,>(operation: (signal: AbortSignal) => Promise<T>, success: (value: T) => void, ownedWorkspaceRead = false) {
    const generation = contextGeneration.current;
    const controller = new AbortController();
    const isCurrent = () => generation === contextGeneration.current && !controller.signal.aborted;
    pending.current.add(controller);
    setBusy(true); setError(null);
    try {
      const result = await operation(controller.signal);
      if (isCurrent()) success(result);
    } catch (failure) {
      if (isCurrent()) {
        // A missing incident preview does not revoke an already open workspace.
        if (invalidatesContext(failure) && (failure.code !== "NOT_FOUND" || ownedWorkspaceRead)) invalidateContext(failure);
        else setError(failure instanceof Error ? failure.message : "Unable to load workspace. Retry the request.");
      }
    } finally {
      pending.current.delete(controller);
      if (isCurrent()) setBusy(pending.current.size > 0);
    }
  }

  useEffect(() => {
    const investigation = new URL(window.location.href).searchParams.get("investigation");
    if (investigation) void run(signal => loadWorkspace(investigation, signal), showWorkspace, true);
    const requests = pending.current;
    return () => { contextGeneration.current++; requests.forEach(controller => controller.abort()); requests.clear(); };
  }, []);

  const updateVersion = useCallback((version: number) => {
    setWorkspace(current => current && version > current.draft_version ? { ...current, draft_version: version } : current);
  }, []);
  const generation = contextGeneration.current;

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
        {validContext && <CaseWorkspace key={workspaceScope(workspace)} workspace={workspace}
          onVersion={version => { if (generation === contextGeneration.current) updateVersion(version); }}
          onScopeError={failure => { if (generation === contextGeneration.current) invalidateContext(failure); }} />}
        <details className="technical-details workspace-details" open={!validContext}>
          <summary>Workspace details</summary>
          <p className="request-id">Investigation: <code>{workspace.investigation_id}</code></p>
          <p className="request-id">State: <code>{workspace.state_id}</code> · Draft version {workspace.draft_version}</p>
          <button disabled={busy} onClick={() => void run(signal => loadWorkspace(workspace.investigation_id, signal), showWorkspace, true)}>
            Reload saved workspace
          </button>
        </details>
      </>}
    </div>
  );
}
