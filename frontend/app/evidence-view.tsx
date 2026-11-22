import { evidenceGroups, navigateEvidenceLink, outcomeMessage, type CaseEvidence } from "../lib/evidence.ts";
import { associationLabel, groupCount, isLimitationField, isTechnicalField, recordSummary, sharedSyntheticLimitation,
  sourceLabels, summaryTimestamp } from "../lib/evidence-presentation.ts";
import type { CaseSummary, ThreadKind } from "../lib/investigations.ts";

export type EvidenceViewResult = { status: "idle" | "loading" } | { status: "failed"; message: string } | { status: "ready"; data: CaseEvidence };

// Plain React text preserves unfamiliar fields and treats source content as data.
function readableValue(value: unknown): React.ReactNode {
  if (value === null) return <span className="muted">null</span>;
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, i) => <li key={i}>{readableValue(item)}</li>)}</ul> : "[]";
  if (typeof value === "object" && value !== null) return fields(value as Record<string, unknown>);
  return String(value);
}
function fields(values: Record<string, unknown>) {
  return <dl className="evidence-fields">{Object.entries(values).map(([key, value]) => <div key={key} className={isLimitationField(key) ? "record-limitation" : undefined}>
    <dt>{key}</dt><dd>{readableValue(value)}</dd>
  </div>)}</dl>;
}

export function EvidenceView({ result, retry, history, selectedCase, onInspect, idPrefix = "", thread }: {
  result: EvidenceViewResult; retry?: string; history: string[]; selectedCase: CaseSummary; onInspect: () => void;
  idPrefix?: string; thread?: ThreadKind;
}) {
  const data = result.status === "ready" ? result.data : undefined;
  const records = data?.groups.flatMap(g => g.sources.flatMap(s => s.records)) ?? [];
  return <section className="evidence-panel" aria-label={`Evidence for ${selectedCase.case_reference}`}>
    <div className="evidence-toolbar">
      <div><h4>Evidence inspection</h4>
        <p className="muted">Synthetic records only; no live source is queried. Reinspection reads the pinned evidence.</p></div>
      <button disabled={result.status === "loading"} onClick={onInspect}>
        {result.status === "loading" ? "Retrieving evidence…" : result.status === "idle" ? "Inspect evidence" : retry || result.status === "failed" ? "Retry evidence" : "Inspect again"}
      </button>
    </div>
    {(thread ?? data?.thread_kind) === "possible_duplicates" && <p className="evidence-notice">Multiple payment attempts do not establish multiple customer charges. Independent financial evidence, including bank/settlement records, may still be missing.</p>}
    {result.status === "failed" && <p role="alert" className="failure">{result.message}</p>}
    {data && <p role="status" className="retrieval-status">Retrieval {data.status === "completed" ? "completed" : "partial — some sources failed or were interrupted"}. Evidence completeness is reported separately for each source.</p>}
    {evidenceGroups.map(group => {
      const sources = data?.groups.find(g => g.group_kind === group.kind)?.sources;
      const groupRecords = sources?.flatMap(s => s.records) ?? [];
      return <section key={`${group.kind}:${data?.evidence_request_id ?? result.status}`} className="evidence-group" aria-label={group.label}>
        <div className="evidence-group-heading"><h5>{group.label}</h5><span>{groupCount(sources)}</span></div>
        <div className="source-outcomes">{group.sources.map(key => {
          const source = sources?.find(s => s.source_key === key);
          return <div key={key} className="source-outcome" data-source={key}>
            <h6>{source?.source_name ?? sourceLabels[key]}</h6>
            {!source ? <p>{result.status === "loading" ? "Loading source evidence… Count unknown." : result.status === "failed" ? "Evidence unavailable after retrieval error. Count unknown." : "Not requested · Count unknown"}</p> : <>
              <p className={source.execution_status !== "completed" ? "failure" : undefined}>
                <strong>Retrieval {source.execution_status}</strong> · {source.execution_status === "completed" ? outcomeMessage(source) : "Record count unknown. Retry explicitly."}</p>
              <p className="source-coverage">Evidence completeness: {source.completeness.replaceAll("_", " ")} · Availability: {source.availability.replaceAll("_", " ")}
                {source.match_status === "not_evaluated" && " · Count unknown"}</p>
              {source.limitations.filter(limit => limit !== sharedSyntheticLimitation).map((limit, i) => <p className="source-limitation" key={i}>{limit}</p>)}
            </>}
          </div>;
        })}</div>
        {groupRecords.length > 0 && <details className="source-records" open>
          <summary>Records ({groupRecords.length})</summary>
          {groupRecords.map(record => {
            const summary = recordSummary(record), time = summaryTimestamp(record);
            const related = data!.relationships.filter(link => link.from_record_id === record.evidence_record_id || link.to_record_id === record.evidence_record_id);
            return <details className="evidence-record" key={record.evidence_record_id} id={`evidence-${idPrefix}${record.evidence_record_id}`}>
              <summary>
                <span className="record-identity">{record.evidence_record_id} <span className="muted">· {record.record_type.replaceAll("_", " ")}</span></span>
                <span className="record-message">{summary.label}: {summary.value}</span>
                <span className="record-time">{time ? `${time.role}: ${time.raw ?? "Not supplied"} · Timezone: ${time.timezone ?? "Unknown"} · Precision: ${time.precision}${time.missing_reason ? ` · ${time.missing_reason}` : ""}` : "Source timestamp not supplied."}</span>
                <span className="record-association">Why related · {associationLabel(record.case_association.category)}: {record.case_association.explanation}</span>
                <span className="sr-only">Source: {record.source_name}. Expand or collapse record details.</span>
              </summary>
              <div className="record-content">
                {fields(Object.fromEntries(Object.entries(record.payload).filter(([key]) => !isTechnicalField(key))))}
                <div className="related-records"><h6>Related records</h6>
                  {related.length === 0 && <p className="muted">No related-record links returned for this record.</p>}
                  {related.map(link => {
                    const targetId = link.from_record_id === record.evidence_record_id ? link.to_record_id : link.from_record_id;
                    const target = records.find(r => r.evidence_record_id === targetId);
                    const descriptionId = `relationship-${idPrefix}${record.evidence_record_id}-${link.relationship_id}`;
                    return <div className="record-relationship" key={link.relationship_id}>
                      {target ? <a href={`#evidence-${idPrefix}${targetId}`} onClick={navigateEvidenceLink} aria-describedby={descriptionId}>
                        {targetId} · {sourceLabels[target.source_key] ?? target.source_name}</a> : <p className="failure">Related record {targetId} is unavailable in this response.</p>}
                      <p id={descriptionId}>{associationLabel(link.basis.category)}: {link.basis.explanation}</p>
                      {link.limitations.map((limit, i) => <p className="source-limitation" key={i}>{limit}</p>)}
                      <details className="evidence-disclosure"><summary>Relationship basis and attribution</summary>
                        <p>{link.from_record_id} → {link.to_record_id}</p>
                        <p>Attribution: {link.attribution}</p><p>Basis record: {link.basis.basis_record_id ?? "Not supplied"}</p>
                        {fields(link.basis.matched_fields)}<p>Relationship ID: {link.relationship_id} · Category: {link.basis.category}</p>
                      </details>
                    </div>;
                  })}
                </div>
                <details className="evidence-disclosure"><summary>Identifiers and source fields</summary>
                  <p>Source: {record.source_name} · Source reference: {record.source_record_reference ?? "Not supplied"}</p>
                  {fields(Object.fromEntries(Object.entries(record.payload).filter(([key]) => isTechnicalField(key))))}
                </details>
                <details className="evidence-disclosure"><summary>Case association and matched fields</summary>
                  <p>{associationLabel(record.case_association.category)}: {record.case_association.explanation}</p>
                  <p>Category: {record.case_association.category} · Basis record: {record.case_association.basis_record_id ?? "Not supplied"}</p>
                  {fields(record.case_association.matched_fields)}
                </details>
                <details className="evidence-disclosure"><summary>Original timestamps and provenance</summary>
                  {record.timestamps.length === 0 && <p>Source timestamp not supplied.</p>}
                  {record.timestamps.map((time, i) => <div key={i} className="original-timestamp">
                    <p>{time.role}: {time.raw ?? "Not supplied"} · Timezone: {time.timezone ?? "Unknown"} · Precision: {time.precision}</p>
                    {time.missing_reason && <p>{time.missing_reason}</p>}
                    <p>UTC bounds: {time.utc_lower ?? "Not supplied"} → {time.utc_upper ?? "Not supplied"}</p>
                  </div>)}
                  <p>Constructed synthetic fixture · {record.fixture_provenance.version_label} · {record.fixture_provenance.fixture_record_id}</p>
                  <p>{record.fixture_provenance.origin}</p>
                </details>
                <details className="evidence-disclosure original-payload"><summary>Original payload (JSON)</summary>
                  <pre tabIndex={0} aria-label={`Original payload for ${record.evidence_record_id}`}>{JSON.stringify(record.payload, null, 2)}</pre>
                </details>
              </div>
            </details>;
          })}
        </details>}
        {sources && <details className="evidence-disclosure source-metadata"><summary>Source scope and retrieval details</summary>
          {sources.map(source => <div key={source.source_key}><p>{source.source_name} · Source key: {source.source_key}</p>
            <p>Scope: {source.scope ?? "Not supplied"}</p>
            <p>Match status: {source.match_status} · Returned count: {source.returned_count ?? "Unknown"} · Error code: {source.error_code ?? "None supplied"}</p>
            {source.limitations.map((limit, i) => <p key={i}>{limit}</p>)}
          </div>)}
        </details>}
      </section>;
    })}
    {history.length > 0 && <details className="evidence-disclosure request-history"><summary>Requests made in this view ({history.length})</summary>
      <p>Query history is persisted. This list shows requests made in this loaded page; earlier responses are not restored on reload.</p>
      <ol>{history.map((id, i) => <li key={i}><code>{id}</code></li>)}</ol>
    </details>}
  </section>;
}
