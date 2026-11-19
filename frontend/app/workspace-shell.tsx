import type { ReactNode } from "react";
import type { IncidentEntry, ThreadKind, Workspace } from "../lib/investigations";

export type WorkspaceView = "overview" | "evidence";

function observeIncidentHeader(shell: HTMLElement | null) {
  const header = shell?.querySelector<HTMLElement>(":scope > .incident-header");
  if (!shell || !header) return;
  // Measure the border box in CSS pixels; wrapping, text zoom and viewport changes
  // can all change it independently of the workspace's data.
  const updateHeight = () => shell.style.setProperty("--incident-header-height", `${header.getBoundingClientRect().height}px`);
  updateHeight();
  const observer = new ResizeObserver(updateHeight);
  observer.observe(header);
  return () => observer.disconnect();
}

export function IncidentHeader({ incident, dataset_version }: IncidentEntry) {
  return <header className="incident-header">
    <div className="incident-heading">
      <div>
        <p className="eyebrow">Incident <span className="incident-reference">{incident.incident_ref}</span></p>
        <h1>{incident.title}</h1>
      </div>
      <span className="badge synthetic-badge">Synthetic Data</span>
    </div>
    <ul className="incident-metadata" aria-label="Incident metadata">
      <li><span className="severity">{incident.severity ?? "Severity not supplied"}</span></li>
      <li>{incident.region ?? "Region not supplied"}</li>
      <li>{incident.category ?? "Category not supplied"}</li>
      <li>{incident.incident_time.raw ?? "Incident time not supplied"} · {incident.incident_time.timezone ?? "Timezone not supplied"}</li>
    </ul>
    {incident.description && <p className="incident-description">{incident.description}</p>}
    <p className="dataset-label">Pinned dataset <span>{dataset_version.version_label}</span></p>
  </header>;
}

export default function WorkspaceShell({ workspace, thread, view, onThread, onView, children, caseNavigation, evidence, hasSelectedCase = false }: {
  workspace: Workspace; thread: ThreadKind; view: WorkspaceView;
  onThread: (thread: ThreadKind) => void; onView: (view: WorkspaceView) => void; children: ReactNode;
  caseNavigation?: ReactNode; evidence?: ReactNode; hasSelectedCase?: boolean;
}) {
  const activeThread = workspace.threads.find(item => item.thread_kind === thread)!;
  return <section ref={observeIncidentHeader} className="workspace-shell" aria-label="Incident workspace">
    <IncidentHeader incident={workspace.incident} dataset_version={workspace.dataset_version} />
    <div className="workspace-layout">
      <aside className="workspace-rail" aria-label="Workspace navigation">
        <p className="eyebrow rail-label">Investigation threads</p>
        <nav aria-label="Investigation threads" className="thread-nav">
          {workspace.threads.map(item => <button key={item.thread_kind}
            aria-pressed={thread === item.thread_kind} onClick={() => onThread(item.thread_kind)}>
            <span>{item.label}</span><span className="thread-count">{item.case_count}<span className="sr-only"> configured case{item.case_count === 1 ? "" : "s"}</span></span>
          </button>)}
        </nav>
        <div className="rail-boundary">
          <p className="eyebrow">Cases</p>
          {caseNavigation ?? <p>No active case</p>}
        </div>
        <p className="rail-footnote">Read-only investigation<br />Synthetic demo environment</p>
      </aside>
      <div className="workspace-content" tabIndex={-1}>
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">Investigation thread</p>
            <h2 id="thread-heading" tabIndex={-1}>{activeThread.label}</h2>
          </div>
          <span className="badge">{activeThread.case_count} configured case{activeThread.case_count === 1 ? "" : "s"}</span>
        </div>
        <p className="thread-description">{thread === "payment_failures"
          ? "Review reported payment failures and inspect the available source evidence."
          : "Review reports of possible duplicate charges. Multiple attempts do not establish multiple charges."}</p>
        <nav className="workspace-tabs" aria-label="Workspace views">
          <button aria-current={view === "overview" ? "page" : undefined} onClick={() => onView("overview")}>Overview</button>
          <button aria-current={view === "evidence" ? "page" : undefined} onClick={() => onView("evidence")}>Evidence</button>
          <button disabled>Findings <span>Unavailable</span></button>
        </nav>
        <div hidden={view !== "overview"} aria-labelledby="thread-heading">
          {children}
        </div>
        <div hidden={view !== "evidence" || !hasSelectedCase}>{evidence}</div>
        {view === "evidence" && !hasSelectedCase && <section className="empty-state" aria-labelledby="select-case-heading">
          <span className="empty-state-icon" aria-hidden="true">↳</span>
          <h3 id="select-case-heading">Select a case</h3>
          <p>Evidence is scoped to an individual case. Choose a case in Overview or the case navigation.</p>
          <p>Case selection opens Evidence. Retrieval requires an explicit inspection.</p>
          <button onClick={event => {
            onView("overview");
            // This button stays mounted across the controlled view change.
            event.currentTarget.closest(".workspace-content")?.querySelector<HTMLButtonElement>(".workspace-tabs button")?.focus();
          }}>Go to Overview</button>
        </section>}
      </div>
    </div>
  </section>;
}
