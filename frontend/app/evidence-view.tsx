import { evidenceGroups, navigateEvidenceLink, outcomeMessage, type CaseEvidence } from "../lib/evidence.ts";
import type { CaseSummary } from "../lib/investigations.ts";

export type EvidenceViewResult = { status: "idle" | "loading" } | { status: "failed"; message: string } | { status: "ready"; data: CaseEvidence };

export function EvidenceView({ result, retry, history, selectedCase, onInspect, idPrefix = "" }: {
  result: EvidenceViewResult; retry?: string; history: string[]; selectedCase: CaseSummary; onInspect: () => void;
  idPrefix?: string;
}) {
  return <section className="evidence-panel" aria-label={`Evidence for ${selectedCase.case_reference}`}>
    <h4>Evidence · {selectedCase.case_reference}</h4>
    <p>Synthetic records only. Provider completeness is unverified; bank/settlement evidence is not constructed.</p>
    <button disabled={result.status === "loading"} onClick={onInspect}>
      {result.status === "loading" ? "Retrieving evidence…" : result.status === "idle" ? "Inspect evidence" : retry || result.status === "failed" ? "Retry evidence" : "Inspect again"}
    </button>
    {result.status === "failed" && <p role="alert" className="failure">{result.message}</p>}
    {result.status === "ready" && <p role="status">Retrieval {result.data.status}. Query history is persisted; reinspection creates a new request.</p>}
    {evidenceGroups.map(group => {
      const sources = result.status === "ready" ? result.data.groups.find(g => g.group_kind === group.kind)?.sources : undefined;
      return <section key={`${group.kind}:${result.status === "ready" ? result.data.evidence_request_id : result.status}`} className="evidence-group" aria-label={group.label}>
        <h5>{group.label}</h5>
        {!sources && <p role={result.status === "loading" ? "status" : undefined}>
          {result.status === "loading" ? "Loading source evidence…" : result.status === "failed" ? "Evidence unavailable after retrieval error. Count unknown." : "Evidence has not been requested."}</p>}
        {sources?.map(source => <div key={source.source_key}>
          <h6>{source.source_name}</h6>
          <p className={source.execution_status !== "completed" ? "failure" : ""}>{outcomeMessage(source)}</p>
          <p>Coverage: {source.completeness.replaceAll("_", " ")} · Availability: {source.availability.replaceAll("_", " ")}</p>
          {source.scope && <p>Scope: {source.scope}</p>}
          {source.limitations.map((limit, i) => <p key={i}>{limit}</p>)}
          {source.records.map(record => <details key={record.evidence_record_id} id={`evidence-${idPrefix}${record.evidence_record_id}`}>
            <summary>{record.evidence_record_id} · {record.record_type} · {record.source_name}</summary>
            <p>Source reference: {record.source_record_reference ?? "Not supplied"}</p>
            <p>Association ({record.case_association.category}): {record.case_association.explanation}</p>
            <pre>{JSON.stringify(record.case_association.matched_fields, null, 2)}</pre>
            {record.case_association.basis_record_id && <p>Association basis: {record.case_association.basis_record_id}</p>}
            {record.timestamps.length === 0 && <p>Source timestamp not supplied.</p>}
            {record.timestamps.map((time, i) => <p key={i}>{time.role}: {time.raw ?? "Not supplied"} · Timezone: {time.timezone ?? "Unknown"} · Precision: {time.precision} {time.missing_reason && `· ${time.missing_reason}`}</p>)}
            <p>Constructed synthetic fixture · {record.fixture_provenance.version_label} · {record.fixture_provenance.fixture_record_id}</p>
            <p>{record.fixture_provenance.origin}</p>
            <pre>{JSON.stringify(record.payload, null, 2)}</pre>
          </details>)}
        </div>)}
      </section>;
    })}
    {result.status === "ready" && result.data.relationships.length > 0 && <details key={result.data.evidence_request_id}>
      <summary>Record relationships and correlation explanations</summary>
      {result.data.relationships.map(link => <div key={link.relationship_id}>
        <p><a href={`#evidence-${idPrefix}${link.from_record_id}`} onClick={navigateEvidenceLink}>{link.from_record_id}</a> → <a href={`#evidence-${idPrefix}${link.to_record_id}`} onClick={navigateEvidenceLink}>{link.to_record_id}</a></p>
        <p>{link.basis.category}: {link.basis.explanation}</p>
        <p>{link.attribution}</p><pre>{JSON.stringify(link.basis.matched_fields, null, 2)}</pre>
        {link.basis.basis_record_id && <p>Basis: {link.basis.basis_record_id}</p>}
        {link.limitations.map((limit, i) => <p key={i}>{limit}</p>)}
      </div>)}
    </details>}
    {history.length > 0 && <details><summary>Requests made in this view ({history.length})</summary>
      <p>Complete query history is retained across reloads.</p>
      <ol>{history.map((id, i) => <li key={i}><code>{id}</code></li>)}</ol>
    </details>}
  </section>;
}
