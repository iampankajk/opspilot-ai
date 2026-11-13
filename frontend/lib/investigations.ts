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
  constructor(status: number, code: string) {
    super(messages[code] ?? `The request failed (HTTP ${status}).`);
    this.status = status;
    this.code = code;
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

async function request(path: string, signal?: AbortSignal, body?: { incident_id: string }): Promise<unknown> {
  const response = await fetch(`/api/v1/${path}`, {
    method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
    headers: body ? { "Content-Type": "application/json", "X-OpsPilot-Request": "1" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    let code = "HTTP_ERROR";
    try {
      const error: unknown = await response.json();
      if (object(error) && object(error.error) && typeof error.error.code === "string") code = error.error.code;
    } catch { /* A proxy outage may not return API JSON. */ }
    throw new InvestigationAPIError(response.status, code);
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
