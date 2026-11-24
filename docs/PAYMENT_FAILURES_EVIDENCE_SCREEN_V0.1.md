# OpsPilot AI — Payment Failures: Evidence Screen v0.1

> **Current scope — 16 November 2026:** D-030–D-034 approve the evidence-first redesign before Task 5B. Case selection navigates only; evidence retrieval/reinspection/retry is explicit. The assistant and search/filters are deferred; Findings is unavailable. Local UI preservation adds no backend contract. The [UX Blueprint](UX_BLUEPRINT_V0.1.md) governs shared behavior, implementation increments, measurable UX-R acceptance criteria, and the explicit conflict register. Original examples are illustrative; they do not add records, API fields, or implemented features. Approval is design evidence, not implementation or accessibility verification.

**Phase:** Phase 2 — Screen-level UX Design  
**Status:** First-pass design amended by approved evidence-first redesign; implementation pending
**Related documents:** `PRD_V0.1.md`, `docs/UX_BLUEPRINT_V0.1.md`, `docs/PAYMENT_FAILURES_OVERVIEW_SCREEN_V0.1.md`

---

## 1. Purpose

The Evidence screen helps a Payments Operations Engineer inspect the records associated with one selected payment case.

It should make three things easy to understand:

1. What evidence is available from each source?
2. What does each individual record say?
3. Why does OpsPilot associate that record with the selected payment case?

The screen presents evidence; it does not decide the root cause or declare a duplicate charge. Interpretation and claim review happen in Findings.


### Current operation and presentation contract

Use Blueprint §§3–6 and UX-R05–R21. Selecting a case or returning to Evidence does not POST. Without an active case, offer Select a case; without a response, show Not requested/count unknown in all groups. Inspect evidence, Inspect again, and eligible Retry are explicit whole-case operations using existing state/version/retry rules. All six source outcomes arrive in one terminal response; no per-source streaming/retry API is introduced. Preserve source execution, availability, match result, and completeness independently. Completed retrieval does not establish complete coverage. Failed/interrupted/not-evaluated counts are unknown, never zero.

Readable compact rows and inline fields come before exact raw payload/technical disclosures. Keep record IDs, original timestamps/timezones/precision/missing reasons, synthetic provenance, matched fields, relationship category/basis/attribution, and limitations available. Material limitations stay visible beside affected evidence; consolidate repeated generic descriptions. Keep multiple records open. Relationship navigation reveals/focuses its target without another request or closing other records. Compact incident/case context remains visible on desktop without independent sticky source/record/toolbars. Mobile uses the thread/case drawer, not an assistant drawer. Current review progress stays Not started; no findings/review calls or controls.

Session-local state restores per scoped investigation/state/thread/case while the page remains loaded. Full reload uses existing workspace resume and defaults to Payment failures → Overview/no case; it does not restore prior evidence responses or expose full durable request history. Workspace GET/reinspection are not numbered revisions or dataset refresh.

## 2. Entry point and navigation

The usual entry point is selecting a payment case from **Payment Failures → Overview**.

When a case is selected:

- OpsPilot opens the Evidence tab.
- The selected case becomes the active case.
- The evidence list is scoped to records associated with that case in the approved synthetic dataset.
- The selected case identity remains visible while the engineer inspects evidence.

The engineer can also reach Evidence by selecting the Evidence tab directly. In that situation, the current thread and currently selected case remain in context when available.

The screen remains inside the agreed investigation workspace:

- Shared Incident Overview stays at the top.
- Investigation Threads remain in the left sidebar.
- Evidence content occupies the center workspace.
- No assistant panel; use the main width for evidence. Findings remains unavailable.

## 3. Shared incident and thread context

The shared incident header follows the approved UX Blueprint. It displays the incident identity and metadata, one-line description when available, relevant incident timezone, and a persistent **Synthetic Data** indicator for this MVP.

The active investigation thread is **Payment failures**. Switching threads changes central content and restores that thread's valid local case/evidence context; shared incident context remains available.

## 4. Selected payment case context

At the top of the Evidence content, show a compact selected-case summary so the engineer can confirm which case they are inspecting.

Display the available fields:

| Field | Example |
|---|---|
| Case reference | `CASE-001` |
| Customer reference | `CUST-104` |
| Payment reference | `PAY-2041` |
| Amount | `SGD 48.00` |
| Reported issue | Payment failure |
| Payment status | Failed |
| Investigation progress | In progress |

The values above are illustrative only.

### Status distinction

Payment status and investigation progress must remain separate:

- **Payment status** describes the payment or payment attempt based on the available records, such as Failed, Pending, Succeeded or Unknown.
- **Investigation progress** describes the engineer's review progress, such as Not started, In progress or Reviewed.

A payment can be Failed while its investigation is Not started. Reviewed does not mean the payment was fixed or the customer was refunded.

If a field is unavailable, show an explicit unavailable/unknown state rather than inferring a value.

## 5. Evidence organization

Evidence is organized by source, not primarily as a single timeline. All four source sections remain visible, including when no matching records are found.

### 5.1 Internal Payment Records

May contain relevant internal payment records, such as:

- Payment attempts.
- Internal payment status changes and lifecycle events.
- Internal identifiers used to relate the record to the selected case.

The UI must distinguish a payment attempt from provider authorization, capture, settlement or a bank debit. These are different lifecycle concepts and must not be presented as interchangeable.

### 5.2 Stripe / Payment Provider

May contain available provider-side records, such as:

- Provider payment-intent or request references.
- Provider event types and statuses.
- Authorization and capture events, where present in the synthetic dataset.

Do not infer a bank debit from a provider authorization or capture record. Do not conclude that no duplicate debit occurred merely because the available provider extract contains one capture.

### 5.3 Logs & Traces

May contain relevant technical records, such as:

- Application log entries.
- Error or timeout messages.
- Trace and request identifiers.
- Relevant service and timestamp information.

A timeout or error message is an observed technical event. It does not establish the underlying root cause by itself.

### 5.4 Support Tickets

May contain:

- Support ticket reference.
- Ticket creation time.
- Customer-reported issue or short summary.
- Relevant payment or customer references included in the synthetic record.

A customer report is evidence of what was reported; it is not automatically proof of the underlying payment outcome.

## 6. Source section behaviour

Each source section has a visible heading, source name, matching-record count when known, and its record list or state message.

Recommended default behaviour:

- Keep all four source sections visible on the page.
- Expand sections that contain matching records by default.
- Show the empty-state message directly in a section with no matching records.
- Allow an engineer to collapse or expand a section without leaving the page.
- Preserve each section's expanded/collapsed state while the engineer inspects records in the same selected case.

A collapsed section keeps its heading and count/state visible. Empty sections must not disappear.

### 6.1 Empty source section

After the relevant source has been checked in the available dataset, show:

> No matching records found in the available synthetic dataset.

This means the current dataset query did not return a matching record. It does not prove that the event never happened or that no evidence exists in another system.

### 6.2 Other source states

Do not use the same message for different situations:

- **No matching records:** The source was checked and no matching record was returned.
- **Source not included:** The source is not represented in the approved dataset for this exercise.
- **Unable to load:** The application could not retrieve/display the source data. Provide a retry action where appropriate.
- **Loading:** The source data is still being retrieved.

Never label a source as empty when it failed to load.

## 7. Evidence record summary

Each record appears as a compact summary within its source section. The summary should help the engineer decide whether to inspect the full record.

Show the fields available and relevant to that record type:

- Record type or short title.
- Source-specific record identifier.
- Event/creation timestamp, including its timezone when known.
- A short human-readable summary or key status/message.
- The selected case relationship basis: why OpsPilot associates this record with the case.
- A clear expand/collapse affordance.

Do not fabricate missing identifiers, timestamps, status values or relationship explanations. If a timestamp's timezone is unknown, do not silently label it as the incident timezone.

### 7.1 Relationship basis

The relationship explanation is essential. Examples of valid explanations, when supported by the actual synthetic records, include:

- Exact internal payment-attempt ID match.
- Matching provider payment-intent or request ID.
- Matching trace/request ID.
- Explicit payment reference included in the support record.
- A documented lookup result that connects the relevant customer/order/amount to the payment attempts.

The UI must describe the actual basis present in the record. It must not turn a weaker association (for example, same customer, order or amount) into proof that two events are the same payment or that a duplicate debit occurred.

Do not show an unexplained confidence percentage or similarity score in v0.1.

## 8. Expand record details inline

When an engineer clicks a record summary, expand its details inline within the same source section.

The interaction should:

- Keep the engineer on the Evidence screen.
- Preserve the selected payment case and its position in the page.
- Reveal additional structured fields and the full useful record content.
- Keep the source identity and record identifier visible.
- Allow the engineer to collapse the record again.

Multiple records may remain expanded at the same time so the engineer can compare them. Expanding one record must not silently close another.

### 8.1 Detail content

Display the fields available for that record type, with readable labels. For example:

- Internal payment record: attempt/payment references, amount, currency, status, lifecycle event and timestamps.
- Provider record: provider reference, event type, status, amount/currency when present, and provider event time.
- Log/trace record: service, severity when present, message, trace/request reference and event time.
- Support ticket: ticket reference, reported issue, relevant customer/payment references and ticket time.

These are possible fields, not mandatory fields for every record. The actual available synthetic record is authoritative.

If raw or technical payload is useful for a record, present the important human-readable details first and place verbose/raw content in a clearly labelled secondary disclosure. Do not hide the record's key meaning in a large unstructured payload.

## 9. Timestamps and ordering

- Preserve the source event timestamp and its timezone when available.
- Use the incident's relevant timezone for normalized display only when the source timestamp can be reliably converted.
- Make the timezone visible; do not rely on the engineer's device timezone.
- If the timestamp or timezone is unavailable, say so rather than guessing.
- Within a source section, order event records by event time from oldest to newest to help the engineer follow that source's sequence. Records without a usable event time appear after timestamped records and are labelled accordingly.

Evidence remains grouped by source. This ordering does not turn the page into a global chronological timeline.

## 10. Cross-references between records

When one record contains an identifier that matches another record, the detail view may provide a link to that related record within the Evidence page.

Selecting a cross-reference should:

1. Navigate/scroll to the related record's source section.
2. Expand the related record if needed.
3. Briefly highlight the target record.
4. Preserve the selected payment case.

Only provide cross-references supported by explicit identifiers or documented relationships in the dataset. Do not create a relationship just because two records have similar-looking values.

## 11. Search and filtering — deferred

D-030 defers evidence search and filters for the current dataset. Keep all four source headings visible. Source and record expand/collapse remains local navigation, not a search/filter or a new retrieval operation. No query builders, arbitrary date analytics, user-defined joins, or cross-incident search.

## 12. OpsPilot AI Assistant behaviour — future requirement only

The assistant is deferred from this redesign: no right panel, chat control, or assistant call. The following requirements apply only if an assistant feature is separately authorized.

Its working context includes:

- The current incident's shared context.
- The active investigation thread (Payment failures).
- The selected payment case.
- The evidence records available for that case.

The engineer may ask questions about the selected case or records. When the assistant makes a factual statement about a record, it must cite/link to the relevant evidence record.

The assistant must:

- Distinguish an observed event from an explanation or root-cause hypothesis.
- State when evidence is missing, incomplete or inconclusive.
- Avoid treating temporal proximity as proof of causation.
- Avoid treating an internal payment attempt, provider authorization, capture and bank debit as interchangeable.
- Avoid declaring a duplicate debit from matching attempt details alone.
- Never invent records, identifiers, source results or relationships.

Moving between Overview, Evidence and Findings within the same thread should not reset the assistant conversation. Switching investigation threads changes its working context as defined in the UX Blueprint.

## 13. Loading, error and empty states

The screen should handle each of the following distinctly:

### Initial loading

Keep the selected-case context visible where possible and show loading placeholders inside the source sections that are still being retrieved.

### Source outcomes in the terminal response

The current synchronous endpoint returns all six outcomes together. During the request show loading, not invented source progress. After a partial result, show successful records and individual failed/interrupted outcomes together; do not block the successful evidence. Per-source streamed arrival is not implemented or required.

### No matching records in a source

Keep the source section visible and show the empty-state message from Section 6.1.

### Selected case has no matching evidence in any source

Keep all four sections visible. Explain that no matching records were found for this case in the available synthetic dataset. Do not imply that the payment did not happen or that the case is invalid.

### Retrieval/display error

Identify the affected source and show that its records could not be loaded. Offer Retry where appropriate. Do not display an error as an empty result.

### Invalid/stale selected case reference

Explain that the selected case could not be found in the current investigation state and provide a route back to the case list. Follow existing stale-state/version recovery; do not silently switch to another case or imply numbered revision support.

## 14. Navigation and state preservation

- The selected case remains active while the engineer moves between evidence source sections and expands/collapses records.
- Moving between Overview and Evidence preserves valid local case/UI state; Findings is unavailable. Future Findings return navigation remains a later requirement.
- Switching to another case updates the case context and evidence scope.
- Switching investigation threads changes the active thread and its case/evidence context.
- Changing the selected case must not be presented as a new saved revision by itself.

## 15. Accessibility and responsive behaviour

- Source sections and record summaries must be keyboard accessible.
- Expand/collapse controls must expose their state to assistive technology.
- Do not rely on colour alone to communicate payment status, investigation progress, source state or record selection.
- Provide visible focus states for interactive records and cross-references.
- At narrower widths use an accessible thread/case drawer, preserve all four source headings and case context, and keep material limitations readable. The assistant is absent. Apply the Blueprint responsive/WCAG 2.2 AA checks.
- Avoid making the entire record detail available only through hover.

## 16. Out of scope for this screen

The Evidence screen does not:

- Determine or declare the root cause.
- Decide whether a customer was actually debited by their bank.
- Confirm a duplicate charge solely from matching attempts or incomplete provider data.
- Trigger refunds, retries, payment mutations or external write actions.
- Send customer messages or update support tickets.
- Provide incident-wide analytics or arbitrary cross-incident search.
- Replace the Findings tab's claim-level AI proposal and human-review workflow.

## 17. Key UX decisions

| Decision | v0.1 behaviour |
|---|---|
| Evidence organization | Group primarily by the four source types |
| Source visibility | Keep all four source sections visible, including empty sections |
| Selected case | Keep its identity visible at the top of Evidence |
| Record inspection | Expand details inline; do not navigate to a new page |
| Record comparison | Allow multiple records to remain expanded |
| Relationship explanation | Show why each record is associated with the selected case |
| Empty vs error | Distinguish no matching records from a retrieval failure |
| Timestamp display | Preserve source time/timezone; show timezone when known |
| In-section ordering | Oldest-to-newest for timestamped event records |
| AI Assistant / Findings | Assistant deferred; Findings visibly unavailable |
| Mutating actions | No source-system/payment mutations; explicit requests retain internal investigation history under existing contracts |

## 18. Open for later design review

The following details can be refined after the first-pass screen review and before implementation:

- Exact visual density and spacing of record summaries.
- Search/filter deferral is resolved by D-030; no control is required now.
- Exact source-specific fields once the final synthetic record schemas are implemented.
- Compact incident/case context stays visible on desktop; exact coordinated sticky-region geometry is refined against Blueprint acceptance criteria.
- Assistant responsive behavior remains future only; current mobile navigation uses the thread/case drawer.

These open details do not change the agreed high-level structure or the evidence-safety rules above.

---

**Screen principle:** Help the engineer inspect the available records and understand why each is related to the selected payment case, while preserving the distinction between evidence, interpretation and conclusion.
