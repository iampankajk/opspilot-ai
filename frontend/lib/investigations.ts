export type IncidentContext = {
  incident_id: string; incident_ref: string; title: string;
  description: string | null; category: string | null; severity: string | null; region: string | null;
  synthetic: true; source_alert_record_id: string;
  incident_time: { role: string; raw: string | null; timezone: string | null; precision: string;
    utc_lower: string | null; utc_upper: string | null; missing_reason: string | null };
};
export type DatasetVersion = { dataset_version_id: string; version_label: string; fixture_digest: string };
export type IncidentEntry = { incident: IncidentContext; dataset_version: DatasetVersion };
export type Workspace = IncidentEntry & {
  investigation_id: string; state_id: string; draft_version: number;
  threads: { thread_kind: "payment_failures" | "possible_duplicates"; label: string; case_count: number }[];
};

const messages: Record<string, string> = {
  STALE_DRAFT_VERSION: "The draft changed. Reload the saved workspace before retrying.",
  OPERATION_IN_PROGRESS: "An evidence request is still running. Reload the workspace before retrying.",
  INVALID_RETRY_REFERENCE: "This request cannot be retried in the selected case. Reload the workspace.",
  EVIDENCE_RETRIEVAL_FAILED: "Evidence retrieval failed. Reload the workspace, then retry explicitly.",
  STALE_STATE: "The selected state is stale. Reload the saved workspace below before trying again.",
  SESSION_REQUIRED: "Start or resume a demo session above, then try again.",
  SESSION_INVALID: "Your session is invalid. Explicitly start a fresh demo above to continue.",
  SESSION_EXPIRED: "Your session expired. Earlier work cannot be recovered by starting a new visitor.",
  NOT_FOUND: "The requested incident or workspace could not be found.",
  DATASET_UNAVAILABLE: "The configured synthetic dataset is unavailable. Check backend configuration.",
  DATABASE_UNAVAILABLE: "The database is unavailable. Please retry.",
  INITIALIZATION_FAILED: "The workspace could not be initialized. Please retry.",
};

export class InvestigationAPIError extends Error {
  status: number;
  code: string;
  details: { state_id?: string; draft_version?: number; evidence_request_id?: string };
  constructor(status: number, code: string, details: InvestigationAPIError["details"] = {}) {
    super(messages[code] ?? `The request failed (HTTP ${status}).`);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function nullableString(value: unknown) { return value === null || typeof value === "string"; }
function validEntry(value: unknown): value is IncidentEntry {
  if (!object(value) || !object(value.incident) || !object(value.dataset_version)) return false;
  const incident = value.incident, dataset = value.dataset_version;
  return [incident.incident_id, incident.incident_ref, incident.title, incident.source_alert_record_id,
    dataset.dataset_version_id, dataset.version_label, dataset.fixture_digest].every(v => typeof v === "string") &&
    incident.synthetic === true && [incident.description, incident.category, incident.severity, incident.region].every(nullableString) &&
    object(incident.incident_time) && typeof incident.incident_time.precision === "string" &&
    nullableString(incident.incident_time.raw) && nullableString(incident.incident_time.timezone);
}

export function parseWorkspace(value: unknown): Workspace {
  if (!object(value)) throw new Error("The backend returned an unexpected workspace response.");
  const { investigation_id, state_id, draft_version, threads } = value;
  if (!validEntry(value) || typeof investigation_id !== "string" ||
      typeof state_id !== "string" || !Number.isInteger(draft_version) ||
      (draft_version as number) < 0 || !Array.isArray(threads) || threads.length !== 2 ||
      !threads.every(t => object(t) && typeof t.label === "string" && Number.isInteger(t.case_count) &&
        (t.case_count as number) >= 0) ||
      new Set(threads.map(t => t.thread_kind)).size !== 2 ||
      !threads.every(t => ["payment_failures", "possible_duplicates"].includes(t.thread_kind))) {
    throw new Error("The backend returned an unexpected workspace response.");
  }
  return value as Workspace;
}

export async function request(path: string, signal?: AbortSignal, body?: object, timeout = 10_000): Promise<unknown> {
  const response = await fetch(`/api/v1/${path}`, {
    method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
    headers: body ? { "Content-Type": "application/json", "X-OpsPilot-Request": "1" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeout)]) : AbortSignal.timeout(timeout),
  });
  if (!response.ok) {
    let code = "HTTP_ERROR";
    let details: InvestigationAPIError["details"] = {};
    try {
      const error: unknown = await response.json();
      if (object(error) && object(error.error) && typeof error.error.code === "string") {
        code = error.error.code;
        if (object(error.error.details)) {
          const d = error.error.details;
          details = { state_id: typeof d.state_id === "string" ? d.state_id : undefined,
            draft_version: Number.isInteger(d.draft_version) ? d.draft_version as number : undefined,
            evidence_request_id: typeof d.evidence_request_id === "string" ? d.evidence_request_id : undefined };
        }
      }
    } catch { /* A proxy outage may not return API JSON. */ }
    throw new InvestigationAPIError(response.status, code, details);
  }
  return response.json();
}

export async function loadIncident(reference: string, signal?: AbortSignal): Promise<IncidentEntry> {
  const data = await request(`incidents/${encodeURIComponent(reference)}`, signal);
  if (!validEntry(data)) throw new Error("The backend returned an unexpected incident response.");
  return data;
}
export async function createInvestigation(incidentId: string, signal?: AbortSignal): Promise<Workspace> {
  return parseWorkspace(await request("investigations", signal, { incident_id: incidentId }));
}
export async function loadWorkspace(investigationId: string, signal?: AbortSignal): Promise<Workspace> {
  return parseWorkspace(await request(`investigations/${encodeURIComponent(investigationId)}/workspace`, signal));
}

export type ThreadKind = Workspace["threads"][number]["thread_kind"];
export type CaseSummary = {
  case_id: string; case_reference: string; primary_report_record_id: string;
  customer_ref: string | null; reported_order_ref: string | null;
  related_order_refs: { value: string; association: "direct" | "candidate" | "contextual"; basis_record_id: string }[];
  reported_issue: string; reported_money: { amount: string; currency: string } | null;
  reported_at: IncidentContext["incident_time"];
  payment_state: { label: string; basis_record_ids: string[]; limitations: string[] } | null;
  investigation_progress: "not_started";
};
export type CaseList = {
  investigation_id: string; state_id: string; draft_version: number; thread_kind: ThreadKind;
  cases: CaseSummary[];
};

export function parseCaseList(value: unknown, expected: {
  investigation_id: string; state_id: string; thread_kind: ThreadKind;
}): CaseList {
  if (!object(value) || value.investigation_id !== expected.investigation_id ||
      value.state_id !== expected.state_id || value.thread_kind !== expected.thread_kind ||
      !Number.isInteger(value.draft_version) || (value.draft_version as number) < 0 ||
      !Array.isArray(value.cases) || !value.cases.every(c => object(c) &&
        [c.case_id, c.case_reference, c.primary_report_record_id, c.reported_issue].every(v => typeof v === "string") &&
        [c.customer_ref, c.reported_order_ref].every(nullableString) && c.investigation_progress === "not_started" &&
        Array.isArray(c.related_order_refs) && c.related_order_refs.every(r => object(r) &&
          typeof r.value === "string" && typeof r.basis_record_id === "string" &&
          ["direct", "candidate", "contextual"].includes(r.association as string)) &&
        (c.reported_money === null || (object(c.reported_money) &&
          typeof c.reported_money.amount === "string" && /^-?\d+(\.\d+)?$/.test(c.reported_money.amount) &&
          typeof c.reported_money.currency === "string")) &&
        object(c.reported_at) && nullableString(c.reported_at.raw) &&
        (c.payment_state === null || (object(c.payment_state) && typeof c.payment_state.label === "string" &&
          Array.isArray(c.payment_state.basis_record_ids) && c.payment_state.basis_record_ids.every(v => typeof v === "string") &&
          Array.isArray(c.payment_state.limitations) && c.payment_state.limitations.every(v => typeof v === "string"))))) {
    throw new Error("The backend returned an unexpected case-list response.");
  }
  return value as CaseList;
}

export async function loadCases(investigationId: string, stateId: string, thread: ThreadKind,
  signal?: AbortSignal): Promise<CaseList> {
  const path = `investigations/${encodeURIComponent(investigationId)}/threads/${thread}/cases?${new URLSearchParams({ state_id: stateId })}`;
  return parseCaseList(await request(path, signal), {
    investigation_id: investigationId, state_id: stateId, thread_kind: thread,
  });
}
