"use client";

import { useEffect, useState } from "react";
import VisitorSessionPanel from "./visitor-session-panel";
import InvestigationPanel from "./investigation-panel";

type Connection =
  | { status: "checking" }
  | { status: "connected"; requestId: string }
  | { status: "failed"; message: string; requestId: string | null };

export default function Home() {
  const [connection, setConnection] = useState<Connection>({ status: "checking" });
  const [attempt, setAttempt] = useState(0);
  const [visitorEpoch, setVisitorEpoch] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    async function checkConnection() {
      setConnection({ status: "checking" });
      let requestId: string | null = null;
      try {
        const response = await fetch("/api/v1/health", {
          cache: "no-store",
          credentials: "same-origin",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]),
        });
        requestId = response.headers.get("X-Request-ID");
        if (!response.ok) {
          throw new Error(`Backend readiness check failed (HTTP ${response.status}).`);
        }
        const data: unknown = await response.json();
        if (
          typeof data !== "object" || data === null ||
          !("status" in data) || data.status !== "ok" ||
          !("database" in data) || data.database !== "connected" ||
          !("schema" in data) || data.schema !== "current" || !requestId
        ) {
          throw new Error("The backend returned an unexpected readiness response.");
        }
        if (active) setConnection({ status: "connected", requestId });
      } catch (error) {
        if (active) setConnection({
          status: "failed",
          message: error instanceof Error ? error.message : "Unable to reach the backend.",
          requestId,
        });
      }
    }

    void checkConnection();
    return () => { active = false; controller.abort(); };
  }, [attempt]);

  return (
    <main id="main-content">
      <a className="skip-link" href="#investigate-heading">Skip to investigation</a>
      <header className="app-bar">
        <a className="brand" href="/" aria-label="OpsPilot AI home"><span className="brand-mark" aria-hidden="true">O</span>OpsPilot <span>AI</span></a>
        <p className="app-caption">Incident investigation workspace</p>
        <details id="demo-session" className="session-disclosure">
          <summary>Demo session</summary>
          <VisitorSessionPanel onNewSession={() => {
            const url = new URL(window.location.href);
            url.searchParams.delete("investigation");
            window.history.replaceState(null, "", url);
            setVisitorEpoch(value => value + 1);
          }} />
        </details>
      </header>
      <InvestigationPanel key={visitorEpoch} />
      {connection.status === "failed" && <p role="alert" className="failure connection-notice">
        Connection unavailable. {connection.message} Check connection diagnostics below and retry.
      </p>}
      <details className="connection-disclosure">
        <summary>Connection diagnostics</summary>
        <div role="status" aria-live="polite">
          {connection.status === "checking" && <p>Checking backend and database…</p>}
          {connection.status === "connected" && <>
            <p className="success">Connected</p>
            <p>The backend is reachable, PostgreSQL is connected, and the schema is current.</p>
          </>}
          {connection.status === "failed" && <>
            <p className="failure">Connection unavailable</p>
            <p>{connection.message}</p>
            <p>Check the backend process, database connection, and Alembic migration.</p>
          </>}
        </div>
        {connection.status !== "checking" && connection.requestId &&
          <p className="request-id">Request ID: <code>{connection.requestId}</code></p>}
        <button disabled={connection.status === "checking"} onClick={() => setAttempt(n => n + 1)}>
          Check again
        </button>
      </details>
    </main>
  );
}
