"use client";

import { useEffect, useRef, useState } from "react";
import { createInvestigation, loadIncident, loadWorkspace, type IncidentEntry, type Workspace } from "../lib/investigations";

export default function InvestigationPanel() {
  const [reference, setReference] = useState("INC-2026-1042");
  const [entry, setEntry] = useState<IncidentEntry | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [selected, setSelected] = useState("payment_failures");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(new Set<AbortController>());

  function showWorkspace(result: Workspace) {
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

  const incident = workspace?.incident ?? entry?.incident;
  return (
    <section aria-labelledby="investigate-heading">
      <h2 id="investigate-heading">Investigate an incident</h2>
      <p>Use your demo session to open a synthetic incident. Each visitor has an independent workspace.</p>
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
      {busy && <p role="status">Loading workspace…</p>}
      {error && <p role="alert" className="failure">{error}</p>}
      {incident && <div className="incident-context">
        <p className="eyebrow">Synthetic data · {incident.incident_ref}</p>
        <h3>{incident.title}</h3>
        <p>{incident.severity ?? "Severity not supplied"} · {incident.region ?? "Region not supplied"}</p>
        <p>{incident.incident_time.raw ?? "Incident time not supplied"}</p>
        {incident.description && <p>{incident.description}</p>}
      </div>}
      {entry && !workspace && <button disabled={busy} onClick={() => {
        void run(signal => createInvestigation(entry.incident.incident_id, signal), showWorkspace);
      }}>Create or resume investigation</button>}
      {workspace && <>
        <p className="request-id">Investigation: <code>{workspace.investigation_id}</code></p>
        <p className="request-id">State: <code>{workspace.state_id}</code> · Draft version {workspace.draft_version}</p>
        <p className="request-id">Pinned dataset: {workspace.dataset_version.version_label}</p>
        <nav aria-label="Investigation threads" className="thread-nav">
          {workspace.threads.map(thread => <button key={thread.thread_kind} disabled={busy}
            aria-pressed={selected === thread.thread_kind} onClick={() => setSelected(thread.thread_kind)}>
            {thread.label} · {thread.case_count} configured case
          </button>)}
        </nav>
        <p>Case counts come from the pinned synthetic fixture. Case and evidence views are deferred.</p>
        <button disabled={busy} onClick={() => void run(signal => loadWorkspace(workspace.investigation_id, signal), showWorkspace)}>
          Reload saved workspace
        </button>
      </>}
    </section>
  );
}
