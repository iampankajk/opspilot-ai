# Participant Brief — APAC Payment Incident

> **SYNTHETIC EXERCISE MATERIAL — PARTICIPANT COPY**  
> This brief contains only the starting information. Do not attach or share facilitator-only materials with participants.

## Your role

You are the on-call Payments Operations Engineer. At 10:30 AM Singapore Time (SGT, UTC+08:00) on 20 October 2026, you receive an automated payment-monitoring alert for the APAC region.

## Starting alert

- Incident: `INC-2026-1042`
- Alert: Payment failure rate exceeded threshold
- Severity: SEV-2 (High)
- Affected service: Payment Processing
- Alert source: Grafana, delivered through PagerDuty
- Current failure rate: 12.4%; expected rate: below 2%
- Measurement window: 10:25–10:30 AM SGT
- Region: APAC
- Trigger time: 10:30 AM SGT (`2026-10-20T02:30:00Z`)
- Status: Triggered
- Alert includes links to a Grafana dashboard and troubleshooting runbook.

The incident brief also states that Support has received approximately 15 customer complaints, including three reports of possible duplicate charges. These are reports, not verified payment outcomes. The monitoring alert confirms an abnormal payment failure rate; it does not establish duplicate captures or their cause.

## Your task

Investigate the payment-failure incident and assess the possible duplicate-charge reports using the information you consider relevant. Determine what is supported, what is not supported, what remains inconclusive, and what evidence or specialist input you would seek next.

You may request or search for records by naming the source or type of information, relevant identifiers, time range, and filters. The facilitator will provide prepared evidence consistently for equivalent requests. Some information may be unavailable or may not have been constructed for this exercise.

Keep observations, hypotheses, and conclusions distinct. A payment attempt, authorization, capture, settlement, and bank posting are different states. Do not infer a customer's final financial outcome from an attempt or authorization alone.

Use these statuses for each claim you assess:

- **Confirmed:** available evidence supports the claim.
- **Not confirmed:** relevant evidence was examined but did not substantiate the claim; this does not necessarily prove it false.
- **Inconclusive:** evidence is insufficient, unavailable, or ambiguous to assess the claim.

Record your investigation actions, evidence references, reasoning, requests for specialist help, and active versus waiting time in the event log. This is an investigation exercise only; no remediation, refund, or customer communication is authorized or requested.
