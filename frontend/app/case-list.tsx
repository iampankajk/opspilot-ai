"use client";

import { useEffect, useState } from "react";
import { loadCases, type CaseList, type ThreadKind, type Workspace } from "../lib/investigations";

import EvidencePanel from "./evidence-panel";

type Result = { status: "loading" } | { status: "failed"; message: string } | { status: "ready"; data: CaseList };

export default function ThreadCases({ workspace, thread, onVersion }: {
  workspace: Workspace; thread: ThreadKind; onVersion: (version: number) => void;
}) {
  const [result, setResult] = useState<Result>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const { investigation_id, state_id } = workspace;

  useEffect(() => {
    const controller = new AbortController();
    setResult({ status: "loading" });
    void loadCases(investigation_id, state_id, thread, controller.signal).then(data => {
      if (!controller.signal.aborted) { setResult({ status: "ready", data }); onVersion(data.draft_version); }
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ status: "failed", message: error instanceof Error ? error.message : "Unable to load cases." });
    });
    return () => controller.abort();
  }, [investigation_id, state_id, thread, attempt, onVersion]);

  return <div aria-label="Thread cases" aria-live="polite">
    {result.status === "loading" && <p role="status">Loading cases…</p>}
    {result.status === "failed" && <>
      <p role="alert" className="failure">{result.message}</p>
      <button onClick={() => setAttempt(value => value + 1)}>Retry cases</button>
    </>}
    {result.status === "ready" && (result.data.cases.length === 0 ? <p>No cases in this thread.</p> :
      result.data.cases.map(c => <article className="case-summary" key={c.case_id}>
        <h3>{c.case_reference}</h3>
        <p><strong>Reported issue:</strong> {c.reported_issue}</p>
        <dl>
          <dt>Customer reference</dt><dd>{c.customer_ref ?? "Not supplied"}</dd>
          <dt>Reported order</dt><dd>{c.reported_order_ref ?? "Not supplied in the report"}</dd>
          <dt>Reported amount</dt><dd>{c.reported_money ? `${c.reported_money.currency} ${c.reported_money.amount}` : "Not supplied"}</dd>
          <dt>Report created</dt><dd>{c.reported_at.raw ?? "Not supplied"}</dd>
        </dl>
        {c.related_order_refs.map(ref => <p key={ref.value}>
          Related order ({ref.association}): {ref.value} · Basis: <code>{ref.basis_record_id}</code>
        </p>)}
        <p><strong>Payment context:</strong> {c.payment_state?.label ?? "Not established at case level"}</p>
        {c.payment_state && <>
          <p className="request-id">Basis: {c.payment_state.basis_record_ids.join(", ")}</p>
          {c.payment_state.limitations.map(limit => <p key={limit}>{limit}</p>)}
        </>}
        <p className="request-id">Primary report: <code>{c.primary_report_record_id}</code></p>
        <p>Investigation: not started. Reported issues do not establish payment outcomes.</p>
        <EvidencePanel workspace={workspace} thread={thread} selectedCase={c} onVersion={onVersion} />
      </article>))}

  </div>;
}
