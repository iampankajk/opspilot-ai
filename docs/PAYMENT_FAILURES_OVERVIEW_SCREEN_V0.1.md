# OpsPilot AI — Payment Failures Overview Screen v0.1

> **Current scope — 16 November 2026:** D-030–D-034 approve the evidence-first redesign before Task 5B. This screen uses the compact header + desktop navigation rail + Overview/Evidence workspace. Assistant, search/filters, and active Findings are deferred. The [UX Blueprint](UX_BLUEPRINT_V0.1.md) governs shared behavior, implementation increments, measurable UX-R acceptance criteria, and the explicit conflict register. Original examples are illustrative; they do not add records, API fields, or implemented features. Approval is design evidence, not implementation or accessibility verification.

**Design status:** First-pass design amended by approved evidence-first redesign; implementation pending\
**Product phase:** Phase 2 — Screen-level UX Design  
**Screen:** Investigation Workspace → Payment failures → Overview

## 1. Purpose and scope

This screen helps a Payments Operations Engineer understand the payment-failure pattern for the selected incident and identify individual cases that need investigation.

It has two levels of information:

- **Incident-level context:** shared information about the incident, shown in the persistent Incident Overview header.
- **Thread-level information:** configured-case count and individual payment/customer cases. Aggregate metrics remain future-only (§4.2).

The screen does not determine root cause, resolve payments, or perform operational actions. It helps the engineer move from an incident-level pattern to a specific case and its supporting evidence.

## 2. Workspace placement

Use the compact incident header, persistent thread/case navigation rail, and main workspace in the amended Blueprint. Overview and Evidence are active; Findings is labelled unavailable and cannot invoke findings APIs. No assistant panel or reserved right column. Fresh entry defaults to Payment failures → Overview with no selected case. Case selection is explicit.

## 3. Shared Incident Overview header

The header is shared across both investigation threads and the active Overview/Evidence views. Findings is visibly unavailable. Show supplied values and explicit missing states rather than copying illustrative content. It contains:

- Incident ID.
- Incident category.
- Severity.
- Region.
- Incident date and time, including its relevant timezone and UTC offset.
- A one-line incident description, when available.
- A persistent **Synthetic Data** indicator for this MVP.

Illustrative content:

```text
INC-2026-1042                                  [Synthetic Data]
Payment Processing · SEV-2 · APAC
20 October 2026 · 10:30 AM SGT (UTC+08:00)
Elevated payment failures and reports of possible duplicate charges across APAC.
```

The incident time is displayed in the incident's relevant timezone, not converted to the engineer's device timezone. The Synthetic Data indicator describes the origin of the dataset; it does not mean the underlying operational problem is fictional as a product use case.

## 4. Payment failures Overview content

### 4.1 Thread heading

At the top of the center content, show:

- The selected thread name: **Payment failures**.
- A brief explanatory line, such as: “Review the payment-failure pattern and the individual cases associated with this incident.”
- **Overview** and **Evidence** navigation, with Overview selected; **Findings — unavailable** is a clearly labelled inactive destination.

### 4.2 Investigation summary metrics — future data-backed capability

For the current redesign, omit aggregate metric cards: the implemented workspace/case APIs do not expose their required basis. Show the configured-case count instead. The definitions and examples below are retained for a later data-backed capability; do not hardcode them or calculate incident-wide rates from the case list.

For the current example incident:

| Metric | Display | Explanation |
|---|---:|---|
| Payment failure rate | **12.4%** | Failed attempts divided by total attempts in the defined window. |
| Failed payment attempts | **62 of 500** | Numerator and denominator are visible so the rate can be understood. |

Show the applicable measurement window directly below the metrics:

`Measurement window: 10:25–10:30 AM SGT (UTC+08:00)`

The metric cards describe the incident-level aggregate pattern. They are **not** a count of individual customers or cases. Do not imply that every failed attempt corresponds to a distinct customer or case.

Metric rules:

- Calculate metrics from the approved dataset; do not manually hardcode display values in the product.
- Keep numerator, denominator, time window and timezone available to the user.
- If a metric cannot be calculated from available evidence, show it as unavailable rather than displaying zero.
- Do not infer a root cause from a metric or from the fact that failures increased.
- These metrics are synthetic for the current MVP and are not live operational measurements.

### 4.3 Individual payment case list

Place **Individual payment cases** below the thread explanation and configured-case count; aggregate cards are absent in this increment.

Each row contains five agreed pieces of information:

| Field | Example |
|---|---|
| Case reference | CASE-001 |
| Customer reference | CUST-104 |
| Payment amount | SGD 48.00 |
| Payment status | Outcome unknown |
| Investigation progress | Not started |

Present Case reference and Customer reference together in the first column. Put the reported issue as a short secondary line beneath the references, for example:

`Reported issue: Customer reports that the payment failed.`

The payment reference can be shown in Evidence when the engineer opens the case; it is not required as a separate column in this Overview list.

#### Payment status and investigation progress are different

**Payment status** describes what the available payment records establish about the payment. Display the source-supported state. Examples may include Failed, Pending, Succeeded or Outcome unknown. Do not label a payment Failed merely because an application recorded a timeout; a timeout may leave the provider outcome unknown.

**Current redesign:** the implemented case contract returns **Not started**. Opening a case, retrieving evidence, or generating a future proposal does not record human review. The following derivation applies when claim-level review is separately implemented in the working state or a saved revision:

- **Not started:** No finding linked to this case has received a human review decision yet, or there are no linked findings to review.
- **In progress:** At least one linked finding has a human review decision, but one or more linked findings still await review.
- **Reviewed:** All currently linked findings have a human review decision.

A human review decision can accept or correct an AI-proposed status. “Reviewed” does not mean the payment succeeded, the issue was resolved, or every possible external source has been checked. Progress is scoped to the current revision; after a dataset refresh creates a new revision, the engineer must review the refreshed evidence and proposals again.

The progress indicator should be derived from claim-level human review records, not from payment status and not from whether the user merely opened the case.

### 4.4 Search and filters — deferred

D-030 defers search and filters for the current dataset. Show every returned case without pagination or sorting controls; no filter toolbar, filter-empty state, or Clear filters action. Larger-list search/filter requirements may be revisited in a separately scoped increment.

### 4.5 Case row interaction

The entire case row is interactive, not just a small button.

When the engineer selects a case:

1. Open the **Evidence** tab.
2. Set the selected case as the active case.
3. Focus the selected-case context. If no local response exists for this scope, show Not requested/count unknown and an explicit Inspect evidence action; selection sends no evidence POST.
4. Keep all four source sections visible: Internal Payment Records, Stripe / Payment Provider, Logs & Traces, and Support Tickets.
5. Preserve a visible case reference so the engineer can tell which case is selected.

Keep the Payment failures thread and selected case identifiable. Do not mix another thread's evidence or local state; the assistant is deferred.

When the engineer returns to Overview, preserve their place and local case selection. Thread switching restores that thread's prior view/case and valid evidence UI state within the current loaded page, as defined in Blueprint §5; full reload retains only the existing backend resume contract.

Keyboard users must be able to focus and activate each row. Use a visible focus style and do not rely on color alone to communicate that a row is clickable.

## 5. Approved desktop structure

```text
┌────────────────────────────────────────────────────────────────┐
│ Incident ID / title · severity · region · time   Synthetic data │
│ Supplied description · pinned dataset               Session    │
├─────────────────┬──────────────────────────────────────────────┤
│ THREADS         │ Payment failures                             │
│ Payment failures│ [Overview] [Evidence] Findings — unavailable  │
│ Possible        │ Configured cases: value from workspace       │
│ duplicates      │                                              │
│ CASES           │ Case/customer | reported amount | payment    │
│ No active case  │ context | review progress                    │
│ until selection │ Select a case → Evidence (no automatic POST) │
└─────────────────┴──────────────────────────────────────────────┘
```

Information architecture only. Use professional dashboard typography, consistent spacing, subtle borders, and compact rows; no source-less metrics or extra sample cases.

## 6. Empty, loading and error states

### No cases in the available synthetic dataset

Show the configured-case count and, in the case-list area:

> No matching payment cases were found in the available synthetic dataset for this investigation.

Do not imply that no real customers or payments were affected outside the dataset.

### No search/filter results — not applicable

Search/filters are deferred; no such state is implemented in this increment.

### Loading

Keep the workspace structure in place and show a restrained case-list loading state, without transient zero counts. Avoid replacing the whole workspace with a blank screen.

### Error loading the thread data

Show:

> We couldn't load the payment-failure investigation data. Try again.

Provide explicit Retry. Do not replace a retrieval error with an empty-case message or display stale cases under another scope.

## 7. Responsive and accessibility behaviour

The MVP is desktop-first because the primary persona is an operations engineer working through several evidence sources.

- On wide screens, use the compact header, persistent navigation rail, and main content workspace.
- At narrower widths, thread/case navigation becomes an accessible drawer; the assistant is absent.
- Keep the Incident Overview information readable when it wraps; do not hide the Synthetic Data indicator.
- On small screens, render each case as a stacked card while preserving the same five fields and full-row interaction.
- Use text labels in addition to status colors.
- Support keyboard navigation, visible unobscured focus, and accessible row-action names. Meet the Blueprint responsive/WCAG 2.2 AA verification targets.

Exact widths, colors, typography and animation are intentionally not specified at this stage.

## 8. Out of scope for this screen

Do not add the following to the MVP Overview screen:

- Refund, retry, cancel, capture or other payment actions.
- Customer messaging or support-ticket updates.
- Bulk accept/review actions.
- Root-cause declaration or automatic resolution.
- Advanced analytics dashboards or cross-incident comparisons.
- Advanced case assignment, ownership or SLA management.
- Live integrations or real customer/payment data.

## 9. Relationship to the other workspace areas

- **Incident Overview header:** shared incident metadata and the one-line incident description.
- **Overview tab:** configured-case count and compact full case list; aggregate metrics await a later supported data contract.
- **Evidence tab:** source records and traceable relationships for the selected case.
- **Findings:** clearly unavailable in this increment; later claims/review remain separate requirements.
- **AI Assistant:** deferred; no panel or conversation controls.

The Payment failures Overview should not duplicate detailed evidence or claim review controls. Its main job is to help the engineer understand the pattern and choose which case to inspect next.

## 10. Current acceptance and future requirements

Use Blueprint UX-R01–R08, R15, and R17–R21. The earlier checked first-pass checklist is superseded as current scope; it was design coverage, not passing implementation checks. Aggregate metrics, search/filters, active Findings/review and assistant behavior remain deferred. Source-safe case selection and full keyboard access remain required.

**Design principle:** The Payment failures Overview gives the engineer a truthful summary of the incident pattern and a clear route into each individual case. It must never confuse a payment outcome with investigation progress or present incomplete evidence as a conclusion.
