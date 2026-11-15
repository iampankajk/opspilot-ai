"use client";

import { useEffect, useRef, useState } from "react";
import { inspectEvidence } from "../lib/evidence";
import { InvestigationAPIError, loadWorkspace, type CaseSummary, type ThreadKind, type Workspace } from "../lib/investigations";

import { EvidenceView, type EvidenceViewResult } from "./evidence-view";

export default function EvidencePanel({ workspace, thread, selectedCase, onVersion }: {
  workspace: Workspace; thread: ThreadKind; selectedCase: CaseSummary; onVersion: (version: number) => void;
}) {
  const [result, setResult] = useState<EvidenceViewResult>({ status: "idle" });
  const [retry, setRetry] = useState<string | undefined>();
  const [history, setHistory] = useState<string[]>([]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function inspect() {
    if (controller.current) return;
    const active = new AbortController(); controller.current = active;
    setResult({ status: "loading" });
    try {
      // Explicitly reconcile interrupted work and use the current committed version before retry.
      const current = await loadWorkspace(workspace.investigation_id, active.signal);
      if (active.signal.aborted) return;
      if (current.state_id !== workspace.state_id) throw new InvestigationAPIError(409, "STALE_STATE");
      onVersion(current.draft_version);
      const data = await inspectEvidence({ investigation_id: workspace.investigation_id, state_id: workspace.state_id,
        thread_kind: thread, case_id: selectedCase.case_id }, current.draft_version, retry, active.signal);
      if (!active.signal.aborted) {
        onVersion(data.draft_version); setResult({ status: "ready", data });
        setHistory(previous => [...previous, data.evidence_request_id]);
        setRetry(data.status === "partial" ? data.evidence_request_id : undefined);
      }
    } catch (error) {
      if (!active.signal.aborted) {
        if (error instanceof InvestigationAPIError) {
          if (error.details.draft_version !== undefined) onVersion(error.details.draft_version);
          if (error.details.evidence_request_id) {
            setRetry(error.details.evidence_request_id);
            setHistory(previous => [...previous, error.details.evidence_request_id!]);
          }
          if (["STALE_STATE", "STALE_DRAFT_VERSION"].includes(error.code)) {
            const current = await loadWorkspace(workspace.investigation_id, active.signal).catch(() => null);
            if (current && !active.signal.aborted) onVersion(current.draft_version);
          }
        }
        if (!active.signal.aborted) setResult({ status: "failed", message: error instanceof Error ? error.message : "Unable to retrieve evidence." });
      }
    } finally { if (controller.current === active) controller.current = null; }
  }

  return <EvidenceView result={result} retry={retry} history={history} selectedCase={selectedCase} onInspect={() => void inspect()} />;
}
