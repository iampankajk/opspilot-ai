# Facilitator Checklist — First Tabletop Exercise

> **FACILITATOR ONLY — contains handling instructions for the evidence catalog.**  
> Keep `docs/SYNTHETIC_EVIDENCE_PACKAGE.md` private to the facilitator. Give participants only `docs/TABLETOP_PARTICIPANT_BRIEF.md` and a blank copy of `docs/TABLETOP_PARTICIPANT_EVENT_LOG_TEMPLATE.md`.

## Before the session

- [ ] Use the frozen `docs/SYNTHETIC_EVIDENCE_PACKAGE.md` as the sole evidence catalog. Do not add records, resolve unknowns, or modify the scenario during the session.
- [ ] Confirm the exercise clock: 20 October 2026, SGT (UTC+08:00); alert at 10:30 AM SGT. Keep fictional incident timestamps separate from actual tabletop session time.
- [ ] Prepare one participant brief and one blank event-log worksheet per participant. Do not share this checklist, the evidence package, its relationship map, availability matrix, release guide, or specialist-response catalog.
- [ ] Confirm that all evidence is labeled and represented as synthetic; no real customer or production records are in use.
- [ ] Prepare a neutral method for recording actual session start/end and participant activity times. Do not infer active effort from event/message timestamps.
- [ ] No simulated specialist waiting time is configured. Do not introduce arbitrary delay.

## Opening

- [ ] Provide only the participant brief and blank event log.
- [ ] Explain that participants may request information by source/type, identifier, time range, and filters; the facilitator will return prepared evidence for equivalent requests consistently.
- [ ] Explain the claim statuses: **Confirmed** means available evidence supports the claim; **Not confirmed** means examined evidence did not substantiate it but does not necessarily prove it false; **Inconclusive** means evidence is insufficient, unavailable, or ambiguous.
- [ ] Explain that active work and waiting are separate measures; facilitator response time is not fictional incident waiting time.
- [ ] Do not suggest a hypothesis, source, identifier, next step, or root cause.

## During the investigation

- [ ] Normalize each request by source, identifier type/value, time range, and filters. Use the package’s facilitator release guide; equivalent requests receive equivalent responses.
- [ ] Release only the evidence matching the participant’s request. Do not volunteer adjacent records or disclose the full inventory, relationship map, availability matrix, or release sequence.
- [ ] Preserve explicit identifier relationships only. Time proximity alone is contextual, not a causal link.
- [ ] Distinguish **not constructed**, **exists but unavailable** (none designated in the frozen package), and **unknown**. Never convert missing evidence into evidence of absence.
- [ ] Preserve source timestamp precision and timezone. Do not invent event, ingestion, or record-creation timestamps.
- [ ] For specialist requests, use the fixed catalog scripts only: return the prepared useful response, clarification prompt, inability to confirm, or not-constructed/unavailable/inaccessible response only when its stated trigger applies. Do not improvise or add technical interpretation.
- [ ] Do not imply that one returned capture proves there was no additional capture; the Stripe event-set completeness is not independently verified. Keep settlement and bank-posting status unknown.
- [ ] Do not imply that the rollout ending at 10:20 proves deployment success or that deployment caused the incident.
- [ ] Do not interpret the shared idempotency key or one returned capture as proof that retry/idempotency logic behaved correctly.
- [ ] Do not authorize or simulate remediation, refunds, or customer communication.
- [ ] Encourage contemporaneous event-log entries without directing their content. Use N/A where an event-log classification does not apply.

## Timing and measurement

- [ ] Record discovery, correlation, interpretation, and specialist-dependency activities separately; record Support handoff repetition as the secondary measure.
- [ ] Record active effort separately from elapsed waiting. Do not infer active review duration from Slack-like timestamps or scenario timestamps.
- [ ] Prevent double-counting overlapping active intervals or concurrent waits. If effort cannot be allocated reliably, mark it unknown rather than estimating.
- [ ] Distinguish facilitator/session elapsed time from fictional scenario time. No specialist wait is scripted in the current package.

## Debrief and close

- [ ] Ask what information the participant requested, what they linked by explicit identifiers, how they evaluated competing hypotheses, and where they retained uncertainty.
- [ ] Ask which work was necessary verification versus possible friction, including any repeated Support searches.
- [ ] Review traceability and reasoning, not agreement with a hidden answer; there is no predetermined root cause or answer key.
- [ ] Label all findings as **synthetic exercise observations**. Do not generalize them to real incidents or claim real-world frequency, severity, savings, or customer impact.
- [ ] Preserve the completed worksheet separately from the blank template. Do not alter the frozen evidence package based on participant conclusions; propose any future package change as a separate review.
