# OpsPilot AI — Possible Duplicates: Evidence Screen v0.1

**Document type:** First-pass screen-level UX specification  
**Phase:** Phase 2 — Screen-level UX Design  
**Status:** Draft for product-owner review  
**Related documents:** `PRD_V0.1.md`, `UX_BLUEPRINT_V0.1.md`, `POSSIBLE_DUPLICATES_OVERVIEW_SCREEN_V0.1.md`, `PAYMENT_FAILURES_EVIDENCE_SCREEN_V0.1.md`

---

## 1. Purpose

The Possible Duplicates → Evidence screen helps a Payments Operations Engineer inspect the source records associated with one possible-duplicate case.

The screen must make it easy to compare internal payment attempts with provider-side payment lifecycle events, technical logs and traces, and the customer support report. It must preserve the distinction between:

- an internal payment attempt;
- a provider request or payment event;
- an authorization;
- a capture; and
- a confirmed customer bank debit or settlement outcome.

The presence of multiple internal attempts is an investigation signal. It is not, on its own, proof that the customer was charged more than once.

This screen presents evidence and relationships. It does not decide whether a duplicate charge occurred or determine a root cause.

## 2. Entry point and navigation

The engineer reaches this screen by selecting a possible-duplicate case from **Possible Duplicates → Overview**.

On entry:

1. Open the Evidence tab.
2. Select the clicked case as the active case.
3. Keep the active case context visible at the top of the main workspace.
4. Show all four evidence-source sections, even when a section has no matching records.
5. Keep the Possible Duplicates thread selected in the left navigation.
6. Keep the AI Assistant available on the right, using the Possible Duplicates thread and active case as its working context.

The engineer can navigate to Overview or Findings without losing the selected investigation thread. Returning to Evidence should preserve the active case when the current investigation revision is unchanged.

## 3. Screen layout

The screen follows the approved investigation workspace structure:

- **Incident Overview:** shared header at the top, including incident ID, category, severity, region, incident date/time, one-line description and Synthetic Data indicator.
- **Investigation Threads:** left sidebar with Payment failures and Possible duplicates.
- **Main Workspace:** center area with Overview, Evidence and Findings tabs.
- **OpsPilot AI Assistant:** persistent, collapsible right-side panel.

Within the center area, the Evidence screen contains:

1. Active possible-duplicate case summary.
2. Evidence completeness and interpretation notice.
3. Optional case-level evidence search, if supported by the current MVP implementation.
4. Four source sections in a stable order.
5. Inline-expanded record details and relationship explanations.

The selected case and the four source sections should remain easy to locate while scrolling. Avoid introducing a separate page for each record.

## 4. Active case summary

At the top of the Evidence content, show the selected possible-duplicate case so the engineer can confirm which report is being investigated.

Display the fields available for the case, such as:

- case reference;
- customer reference;
- order reference;
- reported amount and currency;
- related internal payment references;
- support ticket reference; and
- short reported issue.

Do not fabricate missing identifiers. Omit unavailable optional fields or label them as unavailable, according to the source data.

Example using fictional values:

| Field | Example |
|---|---|
| Case reference | DUP-CASE-001 |
| Customer reference | CUST-204 |
| Order reference | ORDER-8821 |
| Reported amount | SGD 48.00 |
| Reported issue | Customer reports a possible duplicate charge |

The case summary describes what was reported. It must not present the customer's report as a verified duplicate charge.

## 5. Evidence interpretation notice

Show a concise notice near the active case summary:

> Multiple payment attempts do not necessarily mean multiple customer charges. Review the provider payment lifecycle and available settlement evidence before drawing a conclusion.

This notice is persistent on this screen because it addresses the main interpretation risk in possible-duplicate investigations.

The notice is educational, not a finding about the selected case.

## 6. Evidence source sections

The four source sections remain visible in this order, matching the approved Evidence screen pattern:

1. Internal Payment Records
2. Stripe / Payment Provider
3. Logs & Traces
4. Support Tickets

Each section shows:

- source name;
- number of matching records, when a reliable count is available;
- a short description of the records it contains;
- record summary rows/cards;
- timestamps with the source timezone or an explicit timezone indicator; and
- an explanatory empty state when no matching records are available.

Do not hide a source section because it has zero matching records. A zero-result search is not proof that an event did not occur or that no evidence exists elsewhere.

### 6.1 Internal Payment Records

**Purpose:** Show internal payment attempts and lifecycle records related to the possible-duplicate case.

For each record, show available fields such as:

- internal payment attempt/reference;
- customer reference;
- order reference;
- amount and currency;
- attempt status;
- idempotency key, when present;
- creation/update timestamp; and
- any source-defined relationship to the selected case.

When multiple attempts are present, show them as separate records. Do not merge them into a single payment or imply that each attempt resulted in a charge.

If records share an idempotency key, display the matching key and explain that it is a correlation signal. Do not treat key reuse or matching as conclusive proof that the provider processed only one or multiple payments.

When useful, show an attempt comparison with one row per internal attempt. Keep attempt identifiers and statuses distinct.

### 6.2 Stripe / Payment Provider

**Purpose:** Show provider-side records that can help establish the payment lifecycle for the selected case.

For each provider record, show available fields such as:

- provider object/event reference;
- provider event type;
- related payment intent/request reference;
- authorization or capture reference/type, when present;
- amount and currency;
- provider-reported status;
- event timestamp; and
- links to related internal attempts, where a supported relationship exists.

Make the lifecycle meaning of a record explicit. For example, distinguish an authorization event from a capture event. Do not label an authorization or capture as a confirmed bank debit unless the source actually supports that conclusion.

If the provider export or extract has known completeness limitations, display that limitation next to the provider evidence. Do not imply that an absent event was never created or processed.

### 6.3 Logs & Traces

**Purpose:** Show technical records that explain request execution and the interaction between the internal service and provider.

For each record, show available fields such as:

- log or trace reference;
- event timestamp;
- service/component;
- request/trace/correlation identifier;
- relevant event or error summary; and
- relationship to an internal attempt or provider request, when supported.

Logs and traces may explain a timeout or request path. They do not, by themselves, prove whether a provider-side authorization, capture or bank debit occurred.

Avoid presenting temporal proximity as causation. If a log is close in time to an attempt, show the timestamps and supported correlation rather than claiming that one event caused another.

### 6.4 Support Tickets

**Purpose:** Show the customer or support report that initiated or contributed to the possible-duplicate investigation.

For each ticket, show available fields such as:

- ticket reference;
- ticket creation time;
- reported amount/currency, if present;
- customer/order reference, if present;
- concise issue summary; and
- relationship to the selected case.

Clearly distinguish customer-reported information from independently verified payment evidence. A customer statement that they see two charges is a report to investigate, not proof of two successful captures or bank debits.

## 7. Record interaction and inline details

Clicking a record expands its details inline. It does not navigate away from the Evidence screen.

Expanded details may include:

- all relevant source fields available in the synthetic record;
- original source timestamp and timezone;
- source record identifier;
- related identifiers;
- the correlation basis used to associate it with the selected case;
- known limitations or missing fields; and
- links to other evidence records when the relationship is supported.

Multiple records may remain expanded while the engineer compares them. The interface should make expanded records visually distinct without obscuring their source grouping.

An expanded record must preserve the original source meaning. Do not silently normalize different lifecycle events into a generic “payment succeeded” or “payment failed” state.

## 8. Evidence relationships and correlation explanations

When OpsPilot associates two records, show the basis for that relationship in plain language. Examples include:

- matching internal customer reference;
- matching order reference;
- matching amount and currency;
- matching idempotency key;
- explicit provider request/payment reference;
- shared trace or correlation ID; or
- source-provided relationship.

The interface must distinguish:

- **Direct reference match:** a source identifier explicitly points to another record;
- **Field match:** records share one or more attributes, such as customer, order, amount or currency;
- **Temporal proximity:** records occurred near each other in time; and
- **Unverified association:** a possible relationship that needs human inspection.

Do not describe a field match or temporal proximity as a direct reference. Do not turn a possible association into a verified payment lifecycle relationship.

When no supported relationship exists, say so. Do not invent a link merely because two records look similar.

## 9. Payment lifecycle distinctions

The screen must preserve the following distinctions in labels, record details and explanatory copy:

| Concept | What the UI may say | What it must not imply automatically |
|---|---|---|
| Internal attempt | An internal payment attempt was created/recorded | A provider charge occurred |
| Provider request | A request was sent or recorded by the provider | The request completed successfully |
| Authorization | The provider record indicates an authorization | A capture or bank debit occurred |
| Capture | The provider record indicates a capture | Final bank settlement is independently confirmed |
| Bank/settlement evidence | A bank or settlement source reports an outcome | Anything beyond what that source explicitly establishes |
| Timeout | The application/provider interaction timed out or outcome is unknown | The provider definitely did not process the request |

Use the precise status and lifecycle vocabulary present in the source data. If a source does not provide enough detail to identify a lifecycle stage, label the stage as unknown or unavailable rather than inferring it.

## 10. Case-specific synthetic example and expected presentation

The current synthetic exercise includes a possible-duplicate scenario with the following known evidence pattern:

- Support reports a possible duplicate charge.
- Internal Support lookup history returns two internal payment attempts for the same customer/order/amount.
- Both internal attempts use the same idempotency key.
- The internal attempt statuses are timeout and succeeded.
- The available Stripe extract contains one authorization and one capture.
- The completeness of that Stripe extract has not been independently verified.
- Bank/settlement evidence is unavailable.

The Evidence screen should display each of these as source records or source limitations, without collapsing them into a conclusion.

The UI must not state:

- “The customer was charged twice.”
- “The customer was charged only once.”
- “The second attempt was safely deduplicated.”
- “The timeout means the provider did not process the request.”

A suitable neutral summary is:

> Two internal payment attempts are present for the same customer, order and amount, and both show the same idempotency key. The available provider extract contains one authorization and one capture, but its completeness is not independently verified. Bank/settlement evidence is unavailable, so the final customer charge outcome remains unverified.

This is an evidence summary, not a finding or a final decision. Findings and human review belong in the Findings tab.

## 11. Timestamps and timezone handling

- Preserve the source timestamp and its timezone where provided.
- Display a clear timezone label or offset.
- Do not silently convert a source timestamp to the engineer's device timezone.
- If a source timestamp has no known timezone, label the timezone as unknown rather than guessing.
- Where records are compared, make timestamp differences understandable without implying causation.

The shared incident header continues to display the incident's relevant timezone, as defined in the UX Blueprint.

## 12. Search and filtering

For the MVP, prioritize simple case-level evidence discovery:

- A search field may match identifiers and text present in the currently loaded evidence for the selected case.
- If source-level filtering is provided, it should not hide the four source section headings themselves.
- A search with no matches should show a clear no-results message and an easy way to clear the search.
- Do not imply that search covers an external live system. It searches only the evidence available in the current synthetic dataset and investigation revision.

Do not add advanced query builders, arbitrary date-range analytics or cross-incident search to this screen.

## 13. AI Assistant behaviour

The right-side AI Assistant remains available while the engineer inspects records.

Its working context follows the Possible Duplicates thread and selected case. It may help explain the meaning of a record, compare two attempts, or summarize the evidence currently available.

The assistant must:

- cite the evidence records it relies on;
- distinguish source facts from interpretations;
- describe correlation basis and uncertainty;
- avoid claiming a duplicate charge from multiple attempts alone;
- avoid claiming no duplicate charge from an incomplete provider extract;
- avoid treating an authorization or capture as bank settlement unless supported by the source; and
- leave final claim status and human review to the Findings workflow.

The assistant must not trigger refunds, retries, payment mutations, customer messages or any external write action.

## 14. Empty, loading, error and partial-evidence states

### 14.1 Loading

- Show loading feedback within the relevant source section.
- Keep the other source sections visible.
- Do not show a zero-record empty state while a source is still loading.

### 14.2 No matching records

Use a source-specific message such as:

> No matching records found in the available synthetic dataset for this case.

Keep the section visible. Do not state that the source contains no records in general.

### 14.3 Retrieval or parsing error

Show which source could not be loaded and a plain-language explanation, where available. Do not represent an error as an empty result or as proof that no evidence exists.

### 14.4 Partial evidence

When records are available but a source extract is incomplete or its coverage is unknown, show that limitation next to the affected evidence. The screen must not imply complete coverage.

### 14.5 Missing lifecycle stage

If an authorization, capture, settlement or bank outcome is not represented in the available data, label it as unavailable or not present in the available extract. Do not infer the missing event's outcome.

## 15. Accessibility and responsive behaviour

- All expandable records must be keyboard operable.
- Expanded/collapsed state must be announced and visually clear.
- Use text labels in addition to status colors.
- Keep identifiers selectable and readable without relying on color alone.
- On narrower screens, the AI Assistant may collapse into a panel or drawer, but must retain the selected thread and case context.
- Preserve source grouping and active case context on smaller layouts.

## 16. Out of scope

This screen does not:

- determine whether a duplicate customer charge occurred;
- decide the root cause of the incident;
- access bank accounts, card networks or settlement systems not present in the approved dataset;
- initiate refunds, retries, voids, captures or other payment actions;
- modify payment or provider records;
- send customer communications;
- search live Stripe or production systems;
- perform cross-incident analytics; or
- replace human review in the Findings tab.

## 17. Screen acceptance criteria

The first-pass design is acceptable when:

1. The active possible-duplicate case remains visible throughout evidence inspection.
2. All four evidence-source sections remain visible, including empty sections.
3. Records remain grouped by their original source.
4. Selecting a record expands its details inline without leaving the screen.
5. Each displayed record shows its source and available timestamp information.
6. Record relationships include a clear, truthful correlation explanation.
7. Internal attempts remain distinct from provider requests, authorizations, captures and bank/settlement outcomes.
8. Multiple attempts are never presented as proof of multiple customer charges.
9. An incomplete provider extract is never presented as proof that no duplicate charge occurred.
10. Missing evidence, empty results, loading states and retrieval errors are distinguishable.
11. The AI Assistant remains available and follows the Possible Duplicates thread and active case context.
12. The screen provides evidence for human investigation without making a final duplicate-charge or root-cause determination.

---

**Design principle:** Make the payment lifecycle inspectable without overstating what the available records prove. In a possible-duplicate investigation, the difference between an attempt, an authorization, a capture and a settled customer charge must remain visible at every step.
