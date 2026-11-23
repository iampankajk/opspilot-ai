"use client";

import { useState } from "react";
import { bootstrapVisitorSession, type VisitorSession } from "../lib/visitor-session";

export default function VisitorSessionPanel({ onNewSession }: { onNewSession?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<VisitorSession | null>(null);
  const [message, setMessage] = useState("No demo session has been started on this page.");

  async function startOrReuse() {
    setBusy(true);
    try {
      const result = await bootstrapVisitorSession();
      setSession(result.session);
      if (result.created) onNewSession?.();
      setMessage(result.created ? "New anonymous demo session created." : "Existing demo session reused; expiry unchanged.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to initialize session. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="session-panel" aria-labelledby="visitor-heading">
      <h2 id="visitor-heading">Anonymous demo session</h2>
      <p>A lost or expired session cannot recover earlier work. Starting again creates a new visitor.</p>
      <p role="status" aria-live="polite">{busy ? "Initializing session…" : message}</p>
      {session && <details className="technical-details">
        <summary>Session details</summary>
        <p className="request-id">Visitor reference: <code>{session.visitor_context_id}</code></p>
        <p>Expires: <time dateTime={session.expires_at}>{session.expires_at}</time></p>
      </details>}
      <button aria-disabled={busy} onClick={() => { if (!busy) void startOrReuse(); }}>Start or resume demo session</button>
    </section>
  );
}
