import { InvestigationAPIError, type ThreadKind, type Workspace } from "./investigations.ts";

export type CaseLocation = { thread: ThreadKind; view: "overview" | "evidence"; caseId: string | null };
export const initialLocation: CaseLocation = { thread: "payment_failures", view: "overview", caseId: null };
export function workspaceScope(workspace: Workspace): string {
  return JSON.stringify([workspace.investigation_id, workspace.state_id, workspace.dataset_version.dataset_version_id,
    workspace.dataset_version.fixture_digest]);
}
export function invalidatesContext(error: unknown): error is InvestigationAPIError {
  return error instanceof InvestigationAPIError && (error.status === 401 || error.status === 403 ||
    ["STALE_STATE", "NOT_FOUND"].includes(error.code));
}
export function readLocation(value: unknown, scope: string): CaseLocation | null {
  if (!value || typeof value !== "object" || !("scope" in value) || value.scope !== scope || !("location" in value)) return null;
  const location = value.location;
  if (!location || typeof location !== "object" || !("thread" in location) || !("view" in location) || !("caseId" in location)) return null;
  return ["payment_failures", "possible_duplicates"].includes(location.thread as string) &&
    ["overview", "evidence"].includes(location.view as string) && (location.caseId === null || typeof location.caseId === "string")
    ? location as CaseLocation : null;
}
export function locationKey(location: CaseLocation): string {
  return JSON.stringify([location.thread, location.view, location.view === "evidence" ? location.caseId : null]);
}
