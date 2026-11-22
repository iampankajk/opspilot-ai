import type { MouseEvent } from "react";
import { request, type IncidentContext, type ThreadKind } from "./investigations.ts";

export const evidenceGroups = [
  { kind: "internal_payments", label: "Internal Payment Records", sources: ["internal_payments"] },
  { kind: "provider", label: "Stripe / Payment Provider", sources: ["stripe"] },
  { kind: "logs_traces", label: "Logs & Traces", sources: ["loki", "tempo"] },
  { kind: "support_tickets", label: "Support Tickets", sources: ["zendesk", "support_lookup"] },
] as const;
export type Association = { category: string; explanation: string; matched_fields: Record<string, unknown>; basis_record_id: string | null };
export type EvidenceRecord = {
  evidence_record_id: string; source_key: string; source_name: string; record_type: string;
  source_record_reference: string | null; synthetic: true;
  fixture_provenance: { version_label: string; fixture_record_id: string; origin: string };
  timestamps: IncidentContext["incident_time"][]; payload: Record<string, unknown>; case_association: Association;
};
export type SourceOutcome = {
  source_key: string; source_name: string; execution_status: "completed" | "failed" | "interrupted";
  availability: "included" | "not_included" | "not_constructed" | "unavailable";
  match_status: "matches" | "no_matches" | "not_evaluated"; returned_count: number | null;
  records: EvidenceRecord[]; scope: string | null; completeness: string; limitations: string[]; error_code: string | null;
};
export type EvidenceScope = { investigation_id: string; state_id: string; thread_kind: ThreadKind; case_id: string };
export type CaseEvidence = EvidenceScope & {
  request_id: string; evidence_request_id: string; draft_version: number; status: "completed" | "partial";
  groups: { group_kind: string; sources: SourceOutcome[] }[];
  relationships: { relationship_id: string; from_record_id: string; to_record_id: string;
    basis: Association; attribution: string; limitations: string[] }[];
};
function object(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null; }
function strings(v: unknown): v is string[] { return Array.isArray(v) && v.every(x => typeof x === "string"); }
function nullableString(v: unknown) { return v === null || typeof v === "string"; }
function association(v: unknown): v is Association {
  return object(v) && ["direct_ref_match", "documented_lookup", "field_match", "temporal_context", "unverified"].includes(v.category as string) &&
    typeof v.explanation === "string" && object(v.matched_fields) && nullableString(v.basis_record_id);
}
function record(v: unknown, key: string): v is EvidenceRecord {
  return object(v) && v.source_key === key && v.synthetic === true &&
    [v.evidence_record_id, v.source_name, v.record_type].every(x => typeof x === "string") &&
    nullableString(v.source_record_reference) && object(v.fixture_provenance) &&
    [v.fixture_provenance.version_label, v.fixture_provenance.fixture_record_id, v.fixture_provenance.origin].every(x => typeof x === "string") &&
    object(v.payload) && association(v.case_association) && Array.isArray(v.timestamps) && v.timestamps.every(t => object(t) &&
      typeof t.role === "string" && nullableString(t.raw) && nullableString(t.timezone) && nullableString(t.missing_reason) &&
      ["second", "minute", "minute_range", "unknown", "not_applicable"].includes(t.precision as string) &&
      nullableString(t.utc_lower) && nullableString(t.utc_upper));
}
function source(v: unknown): v is SourceOutcome {
  if (!object(v) || typeof v.source_key !== "string" || typeof v.source_name !== "string" ||
    !["completed", "failed", "interrupted"].includes(v.execution_status as string) ||
    !["included", "not_included", "not_constructed", "unavailable"].includes(v.availability as string) ||
    !["matches", "no_matches", "not_evaluated"].includes(v.match_status as string) ||
    !["unverified", "known_partial", "verified_for_stated_scope", "not_applicable"].includes(v.completeness as string) ||
    !nullableString(v.scope) || !strings(v.limitations) || !nullableString(v.error_code) ||
    !Array.isArray(v.records) || !v.records.every(r => record(r, v.source_key as string))) return false;
  if (v.execution_status !== "completed" || v.match_status === "not_evaluated")
    return v.match_status === "not_evaluated" && v.returned_count === null && v.records.length === 0;
  return v.returned_count === v.records.length && v.match_status === (v.records.length ? "matches" : "no_matches");
}
export function parseCaseEvidence(value: unknown, expected: EvidenceScope): CaseEvidence {
  const invalid = () => new Error("The backend returned incomplete or unexpected evidence.");
  if (!object(value) || Object.entries(expected).some(([k, v]) => value[k] !== v) ||
    typeof value.request_id !== "string" || typeof value.evidence_request_id !== "string" ||
    !Number.isInteger(value.draft_version) || (value.draft_version as number) < 0 ||
    !["completed", "partial"].includes(value.status as string) || !Array.isArray(value.groups) || value.groups.length !== 4 ||
    !value.groups.every((g, i) => object(g) && g.group_kind === evidenceGroups[i].kind && Array.isArray(g.sources) &&
      g.sources.length === evidenceGroups[i].sources.length && g.sources.every((s, j) => source(s) && s.source_key === evidenceGroups[i].sources[j])) ||
    !Array.isArray(value.relationships)) throw invalid();
  const data = value as CaseEvidence;
  const records = data.groups.flatMap(g => g.sources.flatMap(s => s.records));
  const ids = new Set(records.map(r => r.evidence_record_id));
  if (ids.size !== records.length || records.length > 14 || data.relationships.length > 14 ||
    !data.relationships.every(r => object(r) && typeof r.relationship_id === "string" && ids.has(r.from_record_id) &&
      ids.has(r.to_record_id) && association(r.basis) && (r.basis.basis_record_id === null || ids.has(r.basis.basis_record_id)) &&
      typeof r.attribution === "string" && strings(r.limitations))) throw invalid();
  const completed = data.groups.flatMap(g => g.sources).filter(s => s.execution_status === "completed").length;
  if (completed === 0 || data.status !== (completed === 6 ? "completed" : "partial")) throw invalid();
  return data;
}
export async function inspectEvidence(scope: EvidenceScope, version: number, retry?: string, signal?: AbortSignal): Promise<CaseEvidence> {
  const path = `investigations/${encodeURIComponent(scope.investigation_id)}/threads/${scope.thread_kind}/cases/${encodeURIComponent(scope.case_id)}/evidence-requests`;
  const data = await request(path, signal, { state_id: scope.state_id, expected_draft_version: version,
    ...(retry ? { retry_of_request_id: retry } : {}) }, 30_000);
  return parseCaseEvidence(data, scope);
}
export function outcomeMessage(source: SourceOutcome): string {
  if (source.execution_status !== "completed") return `${source.source_name}: retrieval ${source.execution_status}. Record count unknown. Retry explicitly.`;
  if (source.availability !== "included") return `Source ${source.availability.replaceAll("_", " ")} in this dataset. Not evaluated.`;
  if (source.match_status === "not_evaluated") return "Source not evaluated. Record count unknown.";
  if (source.match_status === "no_matches") return "No matching records found in the available synthetic dataset for this case.";
  return `${source.returned_count} matching record${source.returned_count === 1 ? "" : "s"} in the available synthetic dataset.`;
}

export function revealEvidenceRecord(target: HTMLDetailsElement): void {
  let ancestor = target.parentElement?.closest("details");
  while (ancestor) { ancestor.open = true; ancestor = ancestor.parentElement?.closest("details"); }
  target.open = true;
}

// Keep the native fragment navigation after revealing its target in this case's panel.
export function navigateEvidenceLink(event: MouseEvent<HTMLAnchorElement>): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const link = event.currentTarget;
  const targetId = link.getAttribute("href")?.slice(1);
  const panel = link.closest(".evidence-panel");
  const target = Array.from(panel?.querySelectorAll<HTMLDetailsElement>("details[id]") ?? [])
    .find(record => record.id === targetId);
  if (target) {
    revealEvidenceRecord(target);
    // Native fragment navigation runs after this click handler and can reset
    // focus. Focus the revealed summary after that default action has completed.
    requestAnimationFrame(() => {
      if (target.isConnected) target.querySelector("summary")?.focus({ preventScroll: true });
    });
  }
}
