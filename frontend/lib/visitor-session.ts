export type VisitorSession = {
  visitor_context_id: string;
  expires_at: string;
};

type BootstrapResult = { session: VisitorSession; created: boolean };
let pending: Promise<BootstrapResult> | null = null;

async function sendBootstrap(): Promise<BootstrapResult> {
  const response = await fetch("/api/v1/visitor-session", {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-OpsPilot-Request": "1" },
    body: "{}",
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status !== 200 && response.status !== 201) {
    throw new Error(`Session initialization failed (HTTP ${response.status}). Try again.`);
  }
  const data: unknown = await response.json();
  if (typeof data !== "object" || data === null ||
      !("visitor_context_id" in data) || typeof data.visitor_context_id !== "string" ||
      !("expires_at" in data) || typeof data.expires_at !== "string") {
    throw new Error("The backend returned an unexpected session response.");
  }
  return { session: { visitor_context_id: data.visitor_context_id, expires_at: data.expires_at },
           created: response.status === 201 };
}

// All callers in this tab share one in-flight bootstrap, including Strict Mode remounts.
export function bootstrapVisitorSession(): Promise<BootstrapResult> {
  if (!pending) pending = sendBootstrap().finally(() => { pending = null; });
  return pending;
}
