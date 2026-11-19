import type { CaseSummary } from "../lib/investigations";

export type CaseListResult = { status: "loading" } | { status: "failed"; message: string } |
  { status: "ready"; cases: CaseSummary[] };

export function CaseDetails({ selectedCase: c }: { selectedCase: CaseSummary }) {
  return <details className="case-identifiers">
    <summary>Case references and association bases</summary>
    <p>Reported order: {c.reported_order_ref ?? "Not supplied in the report"}</p>
    {c.related_order_refs.map(ref => <p key={`${ref.association}:${ref.value}`}>
      Related order ({ref.association}): {ref.value} · Basis: <code>{ref.basis_record_id}</code>
    </p>)}
    <p>Report created: {c.reported_at.raw ?? "Not supplied"} · {c.reported_at.timezone ?? "Timezone not supplied"}</p>
    <p>Primary report: <code>{c.primary_report_record_id}</code></p>
    {c.payment_state && <p>Payment context basis: {c.payment_state.basis_record_ids.join(", ")}</p>}
  </details>;
}

export function CaseContext({ selectedCase: c, contextId }: { selectedCase: CaseSummary; contextId: string }) {
  return <section className="selected-case" aria-labelledby={contextId}>
    <div className="section-heading">
      <h3 id={contextId} tabIndex={-1}>{c.case_reference} <span className="muted">· {c.customer_ref ?? "Customer not supplied"}</span></h3>
      <span className="badge">Review: Not started</span>
    </div>
    <p><strong>Reported concern:</strong> {c.reported_issue}</p>
    <p><strong>Reported amount:</strong> {c.reported_money ? `${c.reported_money.currency} ${c.reported_money.amount}` : "Not supplied"}
      <span className="case-context-payment"><strong>Payment context:</strong> {c.payment_state?.label ?? "Not established at case level"}</span></p>
    {c.payment_state?.limitations.map(limit => <p className="case-limitation" key={limit}>{limit}</p>)}
    <CaseDetails selectedCase={c} />
  </section>;
}

export default function CaseList({ result, selectedCaseId, onSelect, onRetry }: {
  result: CaseListResult; selectedCaseId: string | null; onSelect: (id: string) => void; onRetry: () => void;
}) {
  return <section aria-label="Thread cases">
    <div className="section-heading"><h3>Individual cases</h3><span className="muted">Select a case to open Evidence</span></div>
    {result.status === "loading" && <p role="status">Loading cases…</p>}
    {result.status === "failed" && <><p role="alert" className="failure">{result.message}</p><button onClick={onRetry}>Retry cases</button></>}
    {result.status === "ready" && (result.cases.length === 0 ? <p>No cases in this thread in the available synthetic dataset.</p> :
      <ul className="case-list">{result.cases.map(c => <li key={c.case_id}>
        <button className="case-row" aria-label={`Open Evidence for ${c.case_reference}`} aria-current={selectedCaseId === c.case_id ? "true" : undefined}
          onClick={() => onSelect(c.case_id)}>
          <span className="case-row-identity"><strong>{c.case_reference}</strong><span>{c.customer_ref ?? "Customer not supplied"}</span>
            <span className="case-row-concern">Reported concern: {c.reported_issue}</span>
            <span className="case-order">Reported order: {c.reported_order_ref ?? "Not supplied in the report"}</span>
            {c.related_order_refs.map(ref => <span className="case-order" key={`${ref.association}:${ref.value}`}>
              Related order ({ref.association}): {ref.value} · Basis: {ref.basis_record_id}
            </span>)}</span>
          <span><span className="case-field-label">Reported amount</span>{c.reported_money ? `${c.reported_money.currency} ${c.reported_money.amount}` : "Not supplied"}</span>
          <span><span className="case-field-label">Payment context</span>{c.payment_state?.label ?? "Not established at case level"}
            {c.payment_state?.limitations.map(limit => <span className="case-limitation" key={limit}>{limit}</span>)}</span>
          <span><span className="case-field-label">Review progress</span>Not started<span className="case-row-action">Open Evidence →</span></span>
        </button>
      </li>)}</ul>)}
    <p className="muted case-list-note">Reported concerns do not establish payment outcomes. Opening or inspecting a case does not record human review.</p>
  </section>;
}
