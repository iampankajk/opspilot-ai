# OpsPilot AI — Product Requirements Document v0.1

> **Status:** Approved as the product requirements baseline. This is not implementation-ready and does not validate the real-world problem hypothesis.

## 1. Product overview and vision

OpsPilot AI is a focused operations-investigation assistant for a fictional SaaS company. The proposed MVP helps an on-call Payments Operations Engineer discover and correlate read-only evidence across a bounded set of operational sources and produce a traceable working investigation summary. Hypothesis comparison supports this work; root-cause determination remains human-owned.

The product should make it easier to see what the available evidence establishes, what it merely suggests, and what remains unknown. It is an investigation aid, not an autonomous incident commander or payment operator.

## 2. Problem statement and supporting assumptions

### Problem hypothesis

> An On-call Payments Operations Engineer investigating payment incidents needs to gather and correlate evidence across multiple operational systems. This may involve significant manual effort and make it difficult to maintain a clear, traceable understanding of what the evidence establishes and what remains uncertain.

This is an **unvalidated problem hypothesis**, not a confirmed real-world finding. No user interviews, production incident records, frequency estimates, time savings, financial impact, or customer outcomes are asserted by this PRD.

### Context and evidence status

- `docs/CURRENT_STATE_WORKFLOW.md` describes a detailed **fictional-company workflow assumption** involving monitoring/incident records, payment attempts, provider records, support tickets, logs/traces, deployments, team coordination, and customer financial remediation.
- The APAC incident and 20 October 2026 timestamped records in `docs/SYNTHETIC_EVIDENCE_PACKAGE.md` are **synthetic exercise material**, not evidence that the hypothesized problem occurs in a real company.
- The proposed primary persona is an **assumption to validate**. The user-selected problem framing is a leading hypothesis, not proof of severity or frequency.
- The tabletop is an optional validation activity and is not a prerequisite for reviewing this PRD. Its synthetic observations, if collected, must not be presented as historical or real-world evidence.

### Supporting assumptions to test

1. The engineer routinely needs evidence held in more than one operational source during a payment incident.
2. Identifiers and timestamps can sometimes connect records across those sources, but missing or ambiguous links occur.
3. Seeing source-linked evidence and uncertainty together could help the engineer understand the investigation state.
4. Any efficiency or quality benefit is unknown and must be measured rather than presumed.

## 3. Target persona and user needs

### Primary hypothesized persona — On-call Payments Operations Engineer

Responsible in the fictional workflow for acknowledging and investigating payment incidents, inspecting records, evaluating hypotheses, documenting evidence and uncertainty, coordinating specialist help, and recommending next steps. The Payments Lead / Incident Commander retains overall severity, consequential decision, and closure responsibilities.

### User needs

- Start from a known incident and orient to its scope and time window.
- Find relevant payment, customer-report, provider, and technical evidence without losing source context.
- Understand which records are linked, and why those links are credible.
- Compare evidence that supports, contradicts, or does not resolve an investigative hypothesis.
- Distinguish attempts, authorizations, captures, reversals/refunds, settlement, and bank posting.
- See missing information and unresolved ambiguity without the system filling gaps by guesswork.
- Save and reopen their own working investigation within OpsPilot, retaining evidence references.
- Export a human-reviewed investigation summary as Markdown without writing it back to source systems.

### Secondary roles

Support Engineers, Payments Engineering, SRE/Infrastructure, provider specialists, and the Incident Commander may supply evidence or review findings. They are not separate primary product personas for this proposed MVP.

## 4. Product goals and non-goals

### Goals

1. Help one investigator conduct one bounded payment-incident investigation using the existing synthetic dataset categories as read-only evidence.
2. Prioritize evidence discovery, correlation, and traceable synthesis.
3. Make evidence provenance and explicit record relationships inspectable.
4. Represent observations, hypotheses, proposed claim statuses, and unknowns distinctly; keep root-cause determination human-owned.
5. Support separate investigation threads for elevated payment failures and possible duplicate financial outcomes.
6. Allow the investigator to save/reopen a working investigation and export a reviewed Markdown summary within the product boundary.
7. Evaluate citation/link correctness, uncertainty handling, payment lifecycle distinctions, and unsupported claims using repeatable synthetic cases.

### Non-goals

- Proving the business problem is frequent, costly, or representative based on fictional workflow or tabletop material.
- Autonomously declaring a root cause, incident severity, service recovery, or incident closure.
- Executing remediation, payment routing changes, production changes, retries, refunds, reversals, or customer communications.
- Replacing PagerDuty, Slack, Zendesk, Grafana, Stripe, deployment records, Confluence, Jira, or their owners.
- Managing the full incident lifecycle, post-incident review, refund case lifecycle, or runbook approval lifecycle.
- Connecting to real customer or production systems/data for the portfolio MVP.
- Building a general-purpose autonomous agent, multi-agent system, or arbitrary query executor.
- Selecting implementation architecture, databases, frameworks, infrastructure, or specific vendors in this PRD.

## 5. Agreed direction and proposed MVP boundary

### Product decisions incorporated in this revision

The MVP is a **single-incident, read-only investigation experience** for one investigator role, using synthetic data only. It prioritizes evidence discovery, correlation, and traceable synthesis; hypothesis comparison is supporting functionality, and root-cause determination remains human-owned.

The initial evidence set uses these existing synthetic dataset categories:

- Incident alert.
- Grafana/Prometheus metrics.
- Internal payment records.
- Zendesk tickets and available Support handoff history.
- Stripe provider events.
- Loki logs and Tempo traces.
- Deployment history.

These sources are represented by the existing synthetic dataset. **No live integrations are included.** This is a product-level source boundary, not a choice of storage, connector, or integration architecture.

The interaction model combines a **structured investigation workspace** (incident context, evidence, relationships, hypotheses, and saved summary) with **conversational requests** for targeted evidence discovery and explanation. OpsPilot is not a generic chatbot.

### In-scope

- User-initiated investigation of one incident, with distinct threads for elevated payment failures and possible duplicate-charge reports.
- Read-only retrieval/search over all agreed synthetic evidence categories.
- A structured workspace combined with conversational requests focused on the active investigation.
- Visible evidence references, source names, timestamps/precision, and identifier-based relationships.
- A working summary of observations, hypotheses, evidence for/against, unknowns, and proposed next investigative questions.
- Individual financial assessment of a possible duplicate-charge complaint; no conclusion about bank posting without evidence.
- AI-proposed claim status (Confirmed / Not confirmed / Inconclusive) with evidence references and rationale; the investigator must accept or correct each proposal before it is treated as part of the reviewed summary.
- Individually accept or correct proposed claim statuses; do not offer bulk acceptance.
- Save a numbered working-investigation revision within OpsPilot, preserving AI proposals separately from human decisions/corrections, annotations, timestamps, and evidence references.
- Reopen the exact saved evidence and investigation snapshot, displaying when it was created; do not refresh or alter reviewed conclusions automatically. An intentional refresh reloads the complete evidence set from the current approved synthetic dataset version and creates a new numbered investigation revision. Selective-source and live-source refresh are excluded.
- Make previous reviewed revisions available as read-only history; do not provide collaborative editing, branching, merging, or advanced rollback.
- Export a reviewed summary as Markdown with the agreed content and export timestamp.
- Human review of the investigation output.

**Persistence boundary:** saving/reopening stores numbered investigation revisions inside OpsPilot. Reopening loads the selected snapshot exactly as saved, including the evidence snapshot and review state; it does not fetch fresh source evidence or alter reviewed conclusions. An intentional refresh reloads the entire evidence set from the current approved synthetic dataset version and creates a new numbered revision; selective-source and live-source refresh are excluded. Earlier revisions remain unchanged and available as read-only history. Markdown export produces a user-controlled artifact. None of these behaviors writes findings to PagerDuty, Slack, Zendesk, or any other external source system. Team collaboration and source-system write-back are excluded.

### Explicitly out of scope for the MVP

- Live integrations with PagerDuty, Stripe, Zendesk, Grafana, GitHub, Slack, Confluence, or Jira.
- Bulk incident monitoring, multi-incident analytics, or broad cross-customer trend analysis.
- Team collaboration, shared workspaces for investigations, or external source-system write-back; save/reopen is for the individual investigator within OpsPilot only.
- Sending Slack/Zendesk/customer messages.
- Any payment or production write action, including retry, routing change, rollback, refund, void, or database mutation.
- Approval workflows for actions; no action is executable in this MVP.
- Full incident command, responder scheduling, recovery/closure management, PIR, or financial-remediation case management.
- Predictive root-cause scoring, claims of autonomous root-cause determination, or guaranteed resolution.
- Real customer data, secrets, payment credentials, full card numbers, or CVVs.

## 6. Key user journeys and use cases

### Journey A — Investigate elevated payment failures

1. Engineer opens an existing incident in the investigation experience.
2. Engineer reviews incident context, alert measurements, and time window.
3. Engineer requests or searches relevant evidence using available identifiers and filters.
4. The product presents matching records with their source, timestamp, and explicit link basis.
5. Engineer reviews a summary of observed behavior, evidence limits, plausible hypotheses, and unresolved questions.
6. AI proposes claim statuses with rationale and source references; engineer individually accepts or corrects each proposal (no bulk acceptance), corrects/annotates the working interpretation, and explicitly saves a numbered revision in OpsPilot.
7. On a later reopen, the investigator sees the selected exact evidence/investigation snapshot and its creation time. If new evidence is intentionally refreshed, it becomes a new revision. The investigator may export the reviewed summary as Markdown.

### Journey B — Assess a possible duplicate-charge report

1. Engineer opens a support complaint and inspects available identifiers and their provenance.
2. Engineer searches internal payment attempts and provider lifecycle records.
3. The product shows whether the records establish attempts, authorizations, captures, reversals/refunds, or settlement—without collapsing these states into “charges.”
4. Ambiguous matches remain unresolved; email or approximate time/amount alone cannot create a definitive customer-payment link.
5. The product proposes an appropriately limited status with rationale and identifies evidence still needed, such as provider completeness, settlement, or issuer/bank posting. The engineer accepts or corrects the status before it enters the reviewed summary.

### Core use cases

- Explain what the incident alert establishes and what it does not.
- Find payment attempts related to a complaint using stable identifiers and bounded search criteria.
- Connect internal and provider records only where shared identifiers or explicitly supported relationships exist.
- Retrieve technical evidence for a payment attempt and inspect the matching trace/log context.
- Compare competing hypotheses without treating timing alone as causation.
- Produce a source-linked investigation summary for human review.

## 7. Functional requirements

Priority labels are provisional: **Must** means required for the proposed narrow MVP; **Should** means valuable if it fits the agreed scope; **Open** means product decision needed.

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | Must | Allow an authorized user to start an investigation from a known incident reference and display the incident scope and time window available in the evidence set. |
| FR-02 | Must | Retrieve/search only the approved evidence sources and fields selected for the MVP; evidence-source operations are read-only. Internal saving of the investigator's own working investigation is limited to FR-12. |
| FR-03 | Must | Show each returned record's source identity, available event timestamp, source timezone/precision, and synthetic/fixture provenance where applicable. Do not fabricate missing timestamps. |
| FR-04 | Must | Show why two records are associated, citing shared identifiers or another explicitly supported relationship. Time proximity alone must not be represented as a causal or identity link. |
| FR-05 | Must | Preserve distinct payment lifecycle states: attempt, authorization, capture, reversal/void, refund, settlement, and bank/issuer posting. |
| FR-06 | Must | Represent missing, unavailable, unconstructed, ambiguous, and conflicting evidence distinctly. Do not treat absence from an incomplete extract as proof that an event did not occur. |
| FR-07 | Must | Present an investigation summary organized into observations, hypotheses, supporting/contradicting evidence, limitations, and unresolved questions. |
| FR-08 | Must | Attach inspectable source-record references to factual claims in the summary; unsupported claims must be omitted or explicitly identified as unverified. |
| FR-09 | Must | AI may propose Confirmed, Not confirmed, or Inconclusive for a claim with cited evidence and rationale. The investigator must individually accept or correct each proposal before it appears as an accepted status in the reviewed summary; bulk acceptance is unavailable. A proposal remains separate from the human decision and never becomes an authorized incident decision. |
| FR-10 | Must | Maintain separate investigation threads for elevated failures and suspected duplicate financial outcomes within the same incident. |
| FR-11 | Must | Record the investigation's evidence requests and returned sources so the investigator can reconstruct the investigation path. |
| FR-12 | Must | Every explicit save creates a numbered investigation revision within OpsPilot. Preserve AI proposals separately from human decisions/corrections, annotations, timestamps, and evidence references. |
| FR-13 | Must | Reopen the exact selected saved evidence and investigation snapshot and display its creation time. Do not automatically refresh evidence or modify reviewed conclusions. An intentional refresh reloads the complete evidence set from the current approved synthetic dataset version and creates a new numbered revision; selective-source and live-source refresh are excluded, and prior revisions remain unchanged/read-only. |
| FR-14 | Must | Make previous reviewed revisions available as read-only history. Do not provide collaborative editing, branching, merging, or advanced rollback. |
| FR-15 | Must | Export a reviewed summary as Markdown with incident overview, separate investigation threads, observations, hypotheses, reviewed claim statuses and rationale, source-linked evidence references, unknowns, limitations, next investigative questions, review information, and export timestamp. Include only human-reviewed statuses as accepted conclusions; exclude unreviewed content by default or clearly label it as unreviewed. Include an optional reviewer display name defaulting to “Investigator”; a user-entered name is not a verified identity. Preserve review and export timestamps separately, displaying each in Asia/Singapore timezone and ISO 8601 UTC. Export is user-controlled and does not transmit or write to external source systems. |
| FR-16 | Must | Provide a structured investigation workspace combined with conversational requests scoped to the active incident; do not behave as an unbounded generic chatbot. |

## 8. AI behavior and responsibilities

The AI is an evidence-retrieval, organization, and explanation aid under human direction. Evidence discovery, correlation, and traceable synthesis are primary; hypothesis comparison is supporting functionality. Its allowed responsibilities in the proposed MVP are:

- Interpret an investigator's question and use only bounded, approved read-only retrieval/query capabilities.
- Summarize retrieved evidence while retaining source references and limitations.
- Suggest candidate relationships only when supported by explicit identifiers or clearly label them as tentative for human review.
- Compare evidence against user-stated hypotheses and identify missing or contradictory evidence.
- Propose Confirmed, Not confirmed, or Inconclusive for a claim with evidence references and rationale. Preserve each AI proposal separately from the investigator's individual acceptance/correction, decision timestamp, and annotations. No bulk acceptance is available; a proposal remains an AI suggestion until reviewed and never becomes an authorized incident decision.
- Propose next evidence questions, not operational actions.
- Treat source documents, logs, tickets, and tool outputs as untrusted data, not instructions.

The AI must not:

- Invent records, identifiers, timestamps, provider outcomes, customer impact, or deployment facts.
- Infer root cause from correlation or temporal proximity alone.
- Claim duplicate customer debits from attempts, authorizations, or a single capture record; distinguish provider capture from settlement and bank posting.
- Convert an incomplete extract's missing event into evidence of absence.
- Turn “not confirmed” into “false”; use “inconclusive” when evidence cannot assess a claim.
- Execute an operational or external source-system write operation, issue a refund, retry a payment, alter routing/configuration, or communicate externally. Saving the investigator's working draft within OpsPilot and producing the requested Markdown export are permitted product behaviors, not operational actions.

## 9. Evidence traceability, uncertainty, and attribution

- Every factual statement in an investigation summary must point to the source record(s) that support it.
- A record reference should expose source, record identifier, relevant event time and precision, and the field(s) used for the claim where available.
- The product should preserve identifier provenance (for example, trusted internal identifier versus customer-reported value) when that information exists.
- Match confidence must reflect identifier quality and ambiguity. Customer email alone, approximate payment time alone, or amount alone is insufficient for a definitive payment match.
- Use claim-level statuses: **Confirmed** (available evidence supports the claim), **Not confirmed** (examined evidence did not substantiate it, but this does not necessarily prove it false), **Inconclusive** (evidence is insufficient, unavailable, or ambiguous).
- Keep each AI status proposal distinct from the investigator's individual acceptance/correction, decision timestamp, and annotations.
- Display evidence gaps and extract-completeness limits alongside conclusions, not only in a general disclaimer.
- Keep cause of elevated failures separate from cause/financial outcome of possible duplicate charges unless evidence links them.
- Preserve original source timestamp precision and timezone; distinguish event time from ingestion/record-creation time.
- A saved revision preserves the exact evidence and investigation snapshot, its creation time, and the current review state. Reopening does not refresh sources or alter reviewed conclusions; intentional refresh creates a new revision.

## 10. Human approval and safety boundaries

The proposed MVP performs investigation only and has no operational write actions. A human engineer reviews and owns the working investigation; the Incident Commander / Payments Lead retains incident severity, remediation, recovery, and closure decisions under the fictional workflow assumptions.

Explicitly prohibited in MVP: payments or production mutations; retries; refunds/voids; provider routing changes; deployments/rollbacks; customer-facing messages; and source-system write-back. Because these actions are excluded, an action-approval workflow is not required for v0.1. If a future scope includes an action, it requires separate discovery, explicit authorization rules, human approval, and an auditable action lifecycle before implementation.

## 11. Security, privacy, and access control

- Use only synthetic/demo business data for the portfolio MVP; do not connect to production systems or use real customer records.
- Scope the portfolio MVP to one investigator role. Enterprise RBAC and production-grade authentication decisions are deferred to later design; this scope does not imply readiness for production or sensitive data.
- Use read-only access semantics for every evidence query; no arbitrary model-generated SQL or unrestricted tool execution.
- Do not ingest, display, log, or request full card numbers, CVVs, passwords, payment credentials, or secrets.
- Minimize sensitive identifiers in prompts, logs, and evaluation artifacts; synthetic IDs should be used in the MVP.
- Treat retrieved text and tool output as untrusted content to mitigate prompt-injection and instruction-confusion risks.
- Preserve an audit trail of investigation/query activity appropriate to the eventual design; exact retention and access policy are unresolved.
- Define authorization boundaries, data handling, deletion/retention, and audit access before any future use of non-synthetic data.

## 12. Non-functional requirements

These are proposed product qualities; numeric service-level targets remain open until the intended demo environment and usage are defined.

- **Correctness and traceability:** factual outputs should be verifiable against cited records; unsupported claims are treated as defects.
- **Safety:** default to no-write behavior and fail closed when permissions, source scope, or record relationships are ambiguous.
- **Usability:** an on-call engineer should be able to inspect the evidence basis without needing to trust an opaque final answer.
- **Responsiveness:** investigation steps should provide clear progress and not imply a result while evidence retrieval is pending; latency targets TBD.
- **Reliability:** source errors, unavailable evidence, and partial results should be visible and not silently omitted; availability target TBD for portfolio demo.
- **Auditability:** retain enough activity context to review what was requested and which evidence informed the output; retention policy TBD.
- **Accessibility:** core investigation and evidence-review interactions should be usable with keyboard navigation and readable labels; detailed conformance target TBD.
- **Maintainability/evaluability:** synthetic scenarios and evaluation cases should be repeatable and separable from production-like claims.

## 13. Success metrics and acceptance criteria

### Repeatable synthetic evaluation metrics

The following proposed thresholds are for portfolio MVP acceptance only. They are not real-world performance, frequency, time-saving, or ROI claims. Run a repeatable synthetic test suite covering normal cases, missing evidence, ambiguity, conflicting evidence, and misleading user questions. The project owner is the primary adjudicator. Maintain a reference-evidence manifest for every synthetic test case, specifying expected claim statuses, source record references, relevant fields, and evaluation rationale. Include cases where Inconclusive is the expected status. An independent reviewer may review disputed outcomes when available. This manifest is for repeatable product evaluation only; it is not a hidden answer key for the facilitator-led tabletop. Do not invent root causes.

- **100% citation correctness:** every factual claim has valid supporting citations.
- **100% record-link correctness:** every asserted record link is supported by explicit identifiers or a documented relationship.
- **100% uncertainty handling:** all seeded unknown, incomplete, and ambiguous evidence is handled correctly.
- **100% payment lifecycle distinction correctness:** attempts, authorizations, captures, refunds/reversals, settlement, and bank posting are not conflated.
- **Zero unsupported critical conclusions:** no fabricated root cause or false duplicate-charge claim.
- **100% save/reopen fidelity:** saved evidence snapshots, proposals, human decisions, corrections, annotations, timestamps, and references match the saved revision when reopened.
- **100% Markdown export fidelity:** exported content matches the required reviewed summary content and does not promote unreviewed statuses to accepted conclusions.

These thresholds apply to the defined synthetic suite, not all possible inputs or real-world incidents. Synthetic tabletop observations are not evidence of real-world frequency, savings, or impact. Real-user baselines require separately authorized research.

### Proposed acceptance criteria for the synthetic MVP

1. An investigator can complete the agreed seeded incident investigation using only the approved read-only evidence set.
2. Every factual claim in the generated summary is traceable to one or more displayed records, or explicitly marked unverified/unknown.
3. No record relationship is asserted solely from time proximity, email, approximate amount, or approximate payment time.
4. Ambiguous payment matches remain unresolved; one or multiple attempts are not conflated with captures or bank debits.
5. Incomplete provider evidence is represented as incomplete/unknown; the product does not assert that a missing returned event never occurred.
6. The system distinguishes observations, hypotheses, and claim statuses as defined above, including that “not confirmed” does not mean false.
7. Missing/unavailable/unconstructed evidence and source failures are visibly represented rather than silently treated as negative evidence.
8. Each proposed status is individually accepted or corrected by the investigator; there is no bulk acceptance. The AI proposal and human decision remain separately inspectable.
9. An explicit save creates a numbered revision that preserves proposals, human decisions, corrections, annotations, timestamps, and evidence references; previous reviewed revisions are read-only.
10. Reopening restores the exact selected evidence/investigation snapshot and displays its creation time. It does not refresh data or modify reviewed conclusions. Intentional refresh reloads the complete evidence set from the current approved synthetic dataset version as a new numbered revision; previous revisions remain unchanged and read-only. No live-source or selective-source refresh is included.
11. Markdown export contains incident overview, separate investigation threads, observations, hypotheses, reviewed statuses and rationale, source-linked evidence references, unknowns, limitations, next investigative questions, review information, and export timestamp. Only human-reviewed statuses appear as accepted conclusions; unreviewed content is excluded by default or clearly labeled. Include an optional reviewer display name defaulting to “Investigator,” without representing it as verified identity. Preserve separate review and export timestamps, each displayed in Asia/Singapore timezone and ISO 8601 UTC. Export causes no external write-back.
12. The MVP is scoped to one investigator role and synthetic data only; it cannot execute payment or production actions.
13. The repeatable synthetic test suite covers normal, missing-evidence, ambiguous, conflicting-evidence, and misleading-question cases and meets every threshold listed above. Every case has a reference-evidence manifest defining expected claim statuses, source record references, relevant fields, and rationale; Inconclusive is expected in applicable cases. The project owner is primary adjudicator, with independent review of disputed outcomes when available. This evaluation manifest is not a hidden facilitator answer key and does not establish an invented root cause.

## 14. Risks, dependencies, and unresolved questions

### Risks and dependencies

- **Unvalidated problem:** the hypothesized effort and traceability burden may not be frequent or severe in real practice.
- **Synthetic-evidence bias:** the prepared scenario may make evidence relationships more orderly or more difficult than actual operations.
- **Source/data readiness:** the MVP depends on a coherent, safe, synthetic dataset with explicit identifiers, provenance, timestamp precision, and intentional evidence gaps.
- **False confidence:** fluent summaries could obscure weak matches or incomplete provider evidence unless limitations are prominent.
- **Scope growth:** covering the full incident, approval, remediation, refund, communications, and PIR lifecycle would undermine the narrow investigation focus.
- **Permission boundaries:** source access and role-specific permissions are assumptions requiring future design and validation.
- **Evaluation validity:** synthetic exercise speed or agreement does not establish real business value or correct real-world incident outcomes.

### Next-phase product design questions

The requirements-level choices below are resolved. UX and workflow design should work through presentation and interaction details without changing these boundaries:

1. How should the structured workspace present the incident overview, the two investigation threads, evidence relationships, and uncertainty?
2. What is the clearest review flow for individually accepting or correcting each AI-proposed claim status while keeping proposals separate from human decisions?
3. How should investigators compare numbered revisions, reopen an exact snapshot, and intentionally refresh the complete synthetic evidence set as a new revision?
4. How should Markdown export preview the optional display name and separate review/export timestamps in both required time formats?
5. How should the interface make unknown, incomplete, unavailable, unconstructed, ambiguous, and conflicting evidence understandable without overstating conclusions?
6. What participant-facing and owner-adjudication materials are needed to operate the repeatable synthetic evaluation suite while keeping its reference manifest separate from the optional tabletop facilitator materials?

### Decisions explicitly not made by v0.1

No technical architecture, database, framework, model/provider, agent orchestration, integration protocol, hosting infrastructure, data schema, API design, or production deployment decision is made by this document. The product requirements baseline is approved. The original problem hypothesis remains unvalidated.
