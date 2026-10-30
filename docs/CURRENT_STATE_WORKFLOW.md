# OpsPilot AI — Current-State Incident Workflow

## Purpose and status

This document records the assumed current-state workflow for investigating a fictional SaaS company's APAC payment incident. It is a discovery artifact: it describes the company, users, systems, evidence, responsibilities, decisions, and follow-up as they exist in the scenario.

The workflow is a set of working assumptions for the portfolio scenario, not findings from interviews with a real company or validation of a real operating process. It does not define OpsPilot capabilities, requirements, architecture, or an MVP feature set. Those decisions remain for later discovery and design.

## Scenario

At 10:30 AM, Grafana Alerting detects an unusual increase in payment failures and sends an alert through PagerDuty. The alert reports a 12.4% failure rate against an expected rate below 2% in the last five minutes, affecting Payment Processing in APAC. Around the same time, Support has received about 15 reports of failed payments and three reports of possible duplicate charges. The alert confirms elevated failures; it does not confirm duplicate charges or their cause.

The investigation treats elevated payment failures and possible duplicate captures as related but independent workstreams until evidence establishes a connection.

## Users and responsibilities

| Role | Current responsibilities |
|---|---|
| On-call Payments Operations Engineer | Acknowledges and investigates the incident; examines metrics, transactions, provider records, tickets, logs, traces, and change history; evaluates hypotheses; documents evidence and uncertainty; recommends next steps and remediation; presents recovery evidence. |
| Support Engineer / Support Lead | Supplies customer-reported symptoms and account/order context; helps correlate complaints; communicates verified customer information. The Support Lead reviews customer communications under company policy. |
| Incident Commander / Payments Lead | Owns incident severity, prioritization, coordination, and operational closure; allocates responders; reviews investigation and recovery evidence; decides whether operational recovery and closure criteria are met. |
| Payments Service Engineer | Explains payment-service behavior and changes; supports investigation, validation, and remediation. |
| Release / DevOps Engineer | Helps verify deployment and release history. |
| SRE / Infrastructure Engineer | Investigates regional, network, infrastructure, and runtime configuration issues; maintains observability infrastructure. |
| Finance / Payments Representative | Determines customer financial remedies with the Payments Lead and participates when captures, refunds, settlement, or reconciliation are involved. |
| Finance / Payments Remediation Owner | Owns each confirmed customer financial-remediation case through verified financial outcome and completed customer follow-up. |
| Authorized Finance Approver | Approves refunds according to predefined limits and policy; exceptional or high-value remedies require the applicable additional approval. |
| Authorized Payments Operations Staff | Executes approved payment operations and verifies the provider-side outcome. |
| Service Owner / Senior Engineer and Payments Operations Lead | Review technical accuracy and operational suitability of runbooks; the Payments Operations Lead approves publication. The assigned service owner maintains the approved document. |

## Systems and evidence sources

| System / source | Information used in the investigation |
|---|---|
| Grafana Alerting and PagerDuty | Grafana detects metric threshold breaches. PagerDuty notifies the on-call engineer, supports acknowledgment/ownership/escalation, and holds the central incident timeline. The alert includes incident ID, severity, affected service/region, metric, threshold, time window, trigger time, status, and links to Grafana and a runbook. |
| Grafana dashboards and Prometheus metrics | Payment success/failure rates, attempts, failed counts, volume, baselines, region/provider/method/error-code breakdowns, latency, provider response time, timeouts, retries, and trends over five minutes, 30 minutes, and 24 hours. Metrics show what is happening and how often. |
| Payment Operations Console / transactional PostgreSQL | Internal transaction and payment-attempt records searchable by time, status, region, provider, payment method, transaction ID, or order ID. Details include amount/currency, timestamps, status, sanitized internal/provider errors, provider reference, idempotency key, retry history, latency, and authorization/capture/settlement events where available. It must not expose raw card details or payment credentials. |
| Stripe provider dashboard and records | Provider-side intents/payments, attempts, authorizations, distinct captures and IDs, voids/reversals, refunds, settlement records, response codes, request IDs, idempotency information, and webhook event history. Provider records corroborate internal records. |
| Zendesk | Customer/account identifiers and complaints, ticket time, reported symptoms, approximate payment time, order ID when available, amount/currency, region, and payment method type when available. Customer email alone is not a definitive payment match. Full card numbers, CVVs, passwords, and payment credentials must not be requested or exposed. |
| Grafana Explore with Loki and Tempo | Loki structured logs show individual application events; Tempo traces show request paths, timing, and failure locations. OpenTelemetry provides trace context across service boundaries. Search filters include transaction, attempt, order, provider request, Payment Intent, capture, webhook event, trace/span, or correlation IDs, plus time, service, version, environment, region, provider, error type, and HTTP status. Transaction/customer/trace identifiers are structured fields or metadata, not high-cardinality Loki index labels. |
| GitHub, GitHub Actions, configuration audit logs | GitHub provides source, reviewed pull requests, commits, version-controlled configuration, and release information. GitHub Actions provides build/deployment history, timestamps, application version, environment, region/scope, and deployment status. Configuration audit logs capture runtime, feature-flag, or out-of-band changes and who made them. |
| Slack | Dedicated incident channel for real-time progress, evidence discussion, coordination, escalation, and remediation discussion. Important findings and decisions are copied to the PagerDuty incident record; Slack is not the sole source of truth. |
| Confluence | Approved runbooks, troubleshooting guides, preserved historical incident reports, and the final post-incident report. These document types are distinct. |
| Jira | Engineering and maintenance actions resulting from post-incident review, linked to the incident report and assigned an owner, priority, due date, and acceptance criteria. |
| Git repositories | Version-controlled scripts, configuration, and executable operational procedures where appropriate. |

## Current-state investigation journey

### 1. Detect, notify, acknowledge, and assess

1. Grafana Alerting detects the five-minute payment failure rate breach and sends the alert to PagerDuty.
2. PagerDuty notifies the on-call Payments Operations Engineer. The engineer acknowledges/takes ownership or escalates to another responder.
3. The engineer reviews the alert's metric, threshold, time window, APAC region, affected service, trigger time, and dashboard/runbook links.
4. The Incident Commander / Payments Lead owns severity and investigation prioritization. The current example starts at SEV-2 (High); the team may reassess severity as impact becomes clearer.

### 2. Establish scope and collect customer symptoms

5. The engineer opens Grafana and checks overall health, baseline comparisons, volume, failure categories, geography, provider, payment method, error codes, latency, timeouts, and retries. They compare recent and longer time windows to estimate when the issue began and whether it is worsening.
6. The engineer reviews Zendesk escalations. Support provides symptoms and customer/order context; these reports are additional evidence, not proof of the technical cause or a duplicate charge.
7. The team records the trigger, acknowledgment, timeline, observations, hypotheses, and important decisions in PagerDuty. Slack supports real-time coordination.

### 3. Inspect individual payment attempts and provider state

8. From an aggregate pattern, the engineer searches the Payment Operations Console for affected transactions using time, transaction/order, region, provider, method, status, and available customer/account references.
9. For a possible duplicate charge, the engineer compares internal authorization, capture, settlement, reversal, refund, retry, and idempotency records with Stripe using provider references/Payment Intent IDs, order IDs, amount, currency, timestamps, and event IDs.
10. The investigation distinguishes:
   - Two attempts with one successful capture: not evidence of a duplicate capture.
   - Two distinct successful captures for the same intended order and amount/currency: strong evidence of potential duplicate capture; check reversals, refunds, and settlement.
   - Two authorizations with one capture: not evidence of two captured payments; pending authorizations may be temporary holds.
   - Repeated delivery of one webhook event: not evidence of multiple payments; verify underlying provider objects and distinct capture IDs.
11. Two captures support a duplicate-capture finding. Confirming two posted customer debits may require additional provider or issuer-side evidence. Each customer complaint receives a correlation confidence: high (stable matching identifiers plus corroborating attributes), medium (several attributes but no stable identifier), or insufficient (ambiguous/incomplete). Ambiguous matches remain unresolved; email alone is not enough.

### 4. Examine technical failure evidence and recent changes

12. The engineer uses identifiers from the console and provider records to search Loki logs and Tempo traces in Grafana Explore. They inspect the failure sequence and request path and compare behavior by version, region, service, and time.
13. The engineer compares the first abnormal behavior with relevant GitHub commits/PRs, GitHub Actions deployments, application versions, regions/environments, code/configuration differences, and runtime configuration audit logs. They check whether the affected scope aligns and whether different versions behave differently. Temporal correlation alone does not establish causation.
14. Payments Service, Release/DevOps, and SRE/Infrastructure engineers help explain or verify changes and technical behavior as needed.

### 5. Form, prioritize, and test hypotheses

15. The team considers separate hypotheses for elevated failures and duplicate financial impact. Candidate failure hypotheses include provider degradation, APAC connectivity, a payment service deployment/configuration regression, and retry/idempotency issues. Candidate duplicate-related hypotheses include retry/idempotency defects, duplicate webhook processing, and repeated customer submissions.
16. The Incident Commander / Payments Lead prioritizes work using customer/financial impact, scope, urgency, evidence strength, and investigation feasibility. A potentially serious risk is not ignored solely because evidence is incomplete. The engineer leads technical investigation; Support contributes customer context.
17. The team labels each item as supporting evidence, contradicting evidence, or unverified. Root-cause confidence is classified as confirmed, likely, or inconclusive. Confirmation requires symptom consistency, direct technical evidence, temporal and scope alignment, sufficient examination of alternatives, and validation such as a controlled test, rollback, configuration correction, or recovery observation. Primary causes and contributing factors are recorded separately.

### 6. Coordinate, recommend, and control remediation

18. Findings and material decisions are shared in the incident Slack channel and copied to the PagerDuty record. The record distinguishes observations, hypotheses, and confirmed findings and preserves investigation timestamps, references, evidence, and actions.
19. The Payments Operations Engineer recommends remediation options and evaluates effectiveness, impact, risk/blast radius, reversibility, time, evidence strength, and rollback plan. Containment (reduce ongoing impact), remediation (correct the cause), and recovery (restore and verify normal service) are distinct activities.
20. The Incident Commander / Payments Lead decides which remediation proceeds. Sensitive or consequential operations require explicit authorization under company policy. Low-risk actions may follow previously approved runbooks and delegated permissions. The responsible engineering team executes approved technical remediation and records it in PagerDuty.
21. The team does not blindly retry an uncertain payment, directly manipulate payment records without authorization, or issue a refund without the required approval. Examples of possible technical actions, subject to evidence and policy, include approved provider routing/failover, rollback, correcting unsafe retries, restoring idempotent webhook handling, or controlled request deduplication.

### 7. Verify service recovery and close the operational incident

22. After remediation, the engineer presents recovery evidence; action completion alone is not proof of recovery. The team checks payment success/failure rates and volume against agreed baselines (the scenario's expected failure rate is below 2%), provider and regional health, latency/timeouts/retries, lifecycle consistency, and customer impact.
23. The proposed fictional-company policy requires two consecutive 15-minute healthy windows (30 minutes total), with sufficient transaction volume, no recurring timeout spikes, normalized provider latency/retries, no unexpected duplicate captures, and uncertain outcomes reconciled. Longer observation may be needed for low-volume or high-risk cases.
24. The Incident Commander reviews the evidence and decides service recovery and operational incident closure. Service recovered, customer-impact remediation, and incident closed are separate statuses. Operational closure may occur while refund or customer follow-up remains open, provided those cases continue under their own owners and tracking.

### 8. Verify and manage customer financial remediation

25. For each suspected duplicate, the Payments Operations Engineer confirms two distinct successful captures for the same intended purchase, checks reversals/refunds/settlement, collects provider evidence, and documents whether impact is confirmed, not confirmed, or inconclusive. A duplicate-capture conclusion does not by itself prove two posted customer debits.
26. The Payments Lead and Finance representative determine the remedy based on payment state, provider evidence, impact, and policy. A captured duplicate may call for refunding the additional capture; an outstanding authorization may call for a void/release rather than a refund.
27. An authorized Finance Approver approves financial actions according to limits; high-value/exceptional remedies require additional approval. Authorized Payments Operations Staff execute an approved operation through the Payment Operations Console/provider integration and record capture reference, amount/currency, reason, approver, executor, provider refund reference, timestamp, and status.
28. A refund is not complete merely because it was submitted. Refund status is Pending, Failed, Unknown, or Succeeded. Pending refunds are monitored and escalated to the Payments Operations Lead and Finance after the provider-specific expected window. Failed refunds are investigated, and any further financial operation requires appropriate authorization. Unknown outcomes are reconciled against provider records; no blind resubmission is allowed. Systemic refund failures are escalated to the Incident Commander and tracked separately in Jira.
29. A Finance / Payments Remediation Owner remains accountable for each case through verified financial outcome and the case's closure decision. The Payment Operations Console tracks refund case ID, capture/order/customer references, amount/currency, provider refund ID, request/response times, status, last verification, owner, next follow-up, approval/execution history, and Zendesk ticket. Important status transitions are auditable.
30. The Support Engineer prepares customer communication from verified information; the Support Lead reviews/approves it under policy; the message is sent through Zendesk and associated with the original ticket. PagerDuty contains the incident-level customer impact/remediation summary. Jira tracks systemic engineering work.
31. **Refund execution case closure:** the Finance / Payments Remediation Owner reviews the case and records the final closure decision only when all of the following are satisfied:
   - The provider confirms successful refund processing.
   - Internal and provider records reconcile for the original capture ID, refund ID, amount, and currency.
   - Authorization, executing user, timestamps, and status history are recorded.
   - The customer has been informed of the verified refund outcome through Zendesk.
   - No unresolved refund exceptions or financial discrepancies remain.
   - If the bank has not yet reflected the refund, the expected posting timeframe has been communicated and any needed follow-up is separately tracked.
   - The assigned Finance / Payments Remediation Owner reviews the case and records the closure decision.

   Provider-confirmed refund success does not necessarily mean the customer's bank has posted the credit. If provider processing is confirmed and the above case-closure conditions are met, the refund execution case may be completed while a separate customer/bank-posting follow-up remains open and tracked.

### 9. Review, document, and improve

32. After operational closure, the Incident Commander / Payments Lead facilitates a blameless Post-Incident Review (PIR), with participants selected by incident scope: Operations, Payment Service Engineering, Support, SRE/Infrastructure, and Finance/Payments as relevant.
33. Proposed fictional-company schedule: preserve timeline/evidence during and immediately after the incident; prepare initial documentation within one business day; hold review within three business days; finalize the Confluence report within five business days; track follow-up actions to completion.
34. The PIR covers incident and customer/financial impact, timeline, root cause and evidence, response/recovery effectiveness, what worked or failed, and preventive/corrective actions. Unresolved hypotheses remain marked unresolved even after closure.
35. Jira actions have a clear description, priority, owner, due date, acceptance criteria, and link to the Confluence incident report. Examples include improving timeout monitoring, idempotency, reconciliation, or runbook guidance.
36. Runbooks, troubleshooting guides, incident reports, Jira tasks, and Git-managed scripts/configuration remain distinct. A proposed runbook update is tracked in Jira, drafted by an engineer, reviewed for technical accuracy by the relevant technical owner, approved by the Payments Operations Lead, and published with revision history. Metadata includes document ID/version, owner, reviewer, approver, updated/reviewed/next-review dates, applicable service/environment, and status (Draft, In Review, Approved, Deprecated). Responders use the latest applicable Approved version. A 90-day review cycle is proposed, with earlier review after material service/configuration/operational change. Historical incident reports are preserved.

## Evidence and decision guardrails

- Metrics describe aggregate behavior; logs record events; traces show a request path and where time or failure occurred.
- Alerting establishes an anomaly, not its cause. Aggregate metrics do not establish duplicate charges.
- Attempts, authorizations, captures, settlements, refunds, reversals, and webhook deliveries are distinct payment facts.
- Customer reports are evidence of symptoms; correlation to a payment has an explicit confidence level.
- Findings distinguish observation, hypothesis, and confirmation, and retain contradicting evidence and uncertainty.
- Failure root cause and duplicate financial impact are investigated independently unless evidence connects them.
- Remediation priority does not grant authority to execute. Sensitive operational, financial, and external communication actions follow approval policy.
- Technical recovery, operational incident closure, refund execution case closure, and customer/bank-posting follow-up have separate completion states and owners.
- Sensitive payment credentials and raw card data are not exposed in the investigation workflow.

## Open discovery questions and validation limits

This is internally consistent as a fictional operating model, but it is not validated by real user research. Before converting it into a problem statement or requirements, discovery should still test:

- Whether an on-call Payments Operations Engineer is the best primary user and whether this problem is frequent and costly enough to prioritize.
- Actual time spent, delay points, handoff failures, error rates, and current workarounds across the mapped systems.
- Whether the proposed evidence, confidence, severity, recovery, refund, and approval criteria match company policy and provider-specific realities.
- Which sources are available to an investigator under their actual access permissions and how identifiers are linked across systems.
- Whether the scenario should remain one incident with two parallel workstreams or be modeled as related incident and customer-remediation cases.

No PRD, product feature scope, or OpsPilot solution design is established by this document.
