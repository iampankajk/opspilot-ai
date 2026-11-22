import type { Association, EvidenceRecord, SourceOutcome } from "./evidence.ts";

export const sourceLabels: Record<string, string> = {
  internal_payments: "Internal Payment Records", stripe: "Stripe / Payment Provider",
  loki: "Grafana Loki", tempo: "Grafana Tempo", zendesk: "Zendesk", support_lookup: "Support lookup history",
};

export function associationLabel(category: Association["category"]): string {
  return ({ direct_ref_match: "Direct reference match", documented_lookup: "Documented lookup",
    field_match: "Field match", temporal_context: "Temporal context", unverified: "Unverified association" })[category] ?? category;
}

// Select source wording, never synthesize a lifecycle or financial conclusion.
const summaryFields = ["Internal attempt status", "Internal status", "Returned lifecycle events",
  "Provider Payment Intent status observed in the returned synthetic extract", "Sanitized event",
  "Application span result", "Reported issue", "Search result", "Omitted from packet"];
export function recordSummary(record: EvidenceRecord): { label: string; value: string } {
  const key = summaryFields.find(key => typeof record.payload[key] === "string");
  return key ? { label: key, value: record.payload[key] as string } :
    { label: "Record type", value: record.record_type.replaceAll("_", " ") };
}

export function summaryTimestamp(record: EvidenceRecord) {
  // Prefer a specific event over a generic extract description; keep source text
  // and precision unchanged. All other timestamp roles stay in the disclosure.
  return ["Event time", "Created", "Capture event time"].map(role => record.timestamps.find(t => t.role === role && t.raw))
    .find(Boolean) ?? record.timestamps.find(t => t.raw) ?? record.timestamps[0];
}

export function groupCount(sources?: SourceOutcome[]): string {
  if (!sources || sources.some(s => s.returned_count === null)) return "Count unknown";
  const count = sources.reduce((sum, source) => sum + source.returned_count!, 0);
  return `${count} returned record${count === 1 ? "" : "s"}`;
}

export function isTechnicalField(key: string): boolean {
  return /reference|request|trace id|payment intent$|transaction|customer.*order|customer reference|order reference|idempotency|application version|source system|provenance|timestamp|event time|^created$|^escalated$|^search time$/i.test(key) &&
    !/status|lifecycle|completeness|bank|settlement/i.test(key);
}

export function isLimitationField(key: string): boolean {
  return /completeness|bank|settlement|omitted|other event-specific timestamps/i.test(key);
}

// This exact generic fixture notice is consolidated once above the source groups.
// Every other returned limitation remains visible beside its source.
export const sharedSyntheticLimitation = "Only constructed synthetic records are included; no live source was queried.";
