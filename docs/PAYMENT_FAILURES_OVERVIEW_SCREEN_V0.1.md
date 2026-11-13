# OpsPilot AI — Payment Failures Overview Screen v0.1

**Design status:** First-pass screen design complete; ready for product-owner walkthrough  
**Product phase:** Phase 2 — Screen-level UX Design  
**Screen:** Investigation Workspace → Payment failures → Overview

## 1. Purpose and scope

This screen helps a Payments Operations Engineer understand the payment-failure pattern for the selected incident and identify individual cases that need investigation.

It has two levels of information:

- **Incident-level context:** shared information about the incident, shown in the persistent Incident Overview header.
- **Thread-level information:** payment-failure metrics and individual payment/customer cases, shown in this screen.

The screen does not determine root cause, resolve payments, or perform operational actions. It helps the engineer move from an incident-level pattern to a specific case and its supporting evidence.

## 2. Workspace placement

The screen sits inside the agreed three-part investigation workspace:

- **Left:** Investigation Threads — Payment failures (selected) and Possible duplicates.
- **Center:** Main workspace — Overview, Evidence and Findings tabs.
- **Right:** OpsPilot AI Assistant — remains available while the engineer moves between the tabs.

The shared Incident Overview header remains visible above the workspace.

## 3. Shared Incident Overview header

The header is shared across both investigation threads and all three center tabs. It contains:

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
- The three agreed workspace tabs: **Overview**, **Evidence**, and **Findings**, with Overview selected.

### 4.2 Investigation summary metrics

Show a compact metric area above the case list. Use only metrics supported by the approved synthetic evidence package.

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

Place the heading **Individual payment cases** below the metrics.

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

**Investigation progress** describes the engineer's review of the case in the current saved revision:

- **Not started:** No finding linked to this case has received a human review decision yet, or there are no linked findings to review.
- **In progress:** At least one linked finding has a human review decision, but one or more linked findings still await review.
- **Reviewed:** All currently linked findings have a human review decision.

A human review decision can accept or correct an AI-proposed status. “Reviewed” does not mean the payment succeeded, the issue was resolved, or every possible external source has been checked. Progress is scoped to the current revision; after a dataset refresh creates a new revision, the engineer must review the refreshed evidence and proposals again.

The progress indicator should be derived from claim-level human review records, not from payment status and not from whether the user merely opened the case.

### 4.4 Search and filters

To help an engineer find a case without turning this screen into a case-management system, include a small control row above the list:

- Search by case reference or customer reference.
- Filter by Payment status.
- Filter by Investigation progress.

Defaults:

- Search is empty.
- Both filters are set to **All**.
- No cases are hidden by default.
- Provide a **Clear filters** action when any search or filter is active.

For the synthetic MVP, show the full matching list without pagination. Keep the control set small; advanced query builders, bulk selection and saved filters are out of scope.

### 4.5 Case row interaction

The entire case row is interactive, not just a small button.

When the engineer selects a case:

1. Open the **Evidence** tab.
2. Set the selected case as the active case.
3. Focus the Evidence content on records related to that case.
4. Keep all four source sections visible: Internal Payment Records, Stripe / Payment Provider, Logs & Traces, and Support Tickets.
5. Preserve a visible case reference so the engineer can tell which case is selected.

The right-side AI Assistant remains open and retains the Payment failures thread context. The selected case becomes the current focus within that thread; it does not authorize the assistant to silently mix in Possible duplicates evidence.

When the engineer returns to Overview, preserve the prior search/filter state and their place in the case list during the current workspace session.

Keyboard users must be able to focus and activate each row. Use a visible focus style and do not rely on color alone to communicate that a row is clickable.

## 5. Suggested desktop wireframe

This is a structural wireframe, not a final visual design or pixel specification.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ INC-2026-1042                                      [SYNTHETIC DATA]           │
│ Payment Processing · SEV-2 · APAC                                            │
│ 20 Oct 2026 · 10:30 AM SGT (UTC+08:00)                                       │
│ Elevated payment failures and reports of possible duplicate charges across APAC.│
├────────────────┬───────────────────────────────────────────┬─────────────────┤
│ INVESTIGATION  │ Payment failures                           │ OPSPILOT AI     │
│ THREADS        │ Review the failure pattern and cases.      │                 │
│                │                                             │ Assistant       │
│ > Payment      │ [Overview] [Evidence] [Findings]            │ remains         │
│   failures     │                                             │ available       │
│                │ ┌──────────────────┐ ┌───────────────────┐  │                 │
│   Possible     │ │ 12.4%            │ │ 62 of 500         │  │                 │
│   duplicates   │ │ Failure rate     │ │ Failed attempts   │  │                 │
│                │ └──────────────────┘ └───────────────────┘  │                 │
│                │ Measurement window: 10:25–10:30 AM SGT      │                 │
│                │                                             │                 │
│                │ Individual payment cases                    │                 │
│                │ [Search case/customer] [Payment status ▾]   │                 │
│                │ [Investigation progress ▾] [Clear filters]  │                 │
│                │                                             │                 │
│                │ CASE-001 · CUST-104 | SGD 48.00 | Outcome   │                 │
│                │ Reported issue: Customer reports failure   │                 │
│                │                          | Not started       │                 │
│                │─────────────────────────────────────────────│                 │
│                │ CASE-002 · CUST-108 | SGD 75.00 | Failed    │                 │
│                │ Reported issue: Payment did not complete   │                 │
│                │                          | In progress       │                 │
└────────────────┴───────────────────────────────────────────┴─────────────────┘
```

## 6. Empty, loading and error states

### No cases in the available synthetic dataset

Keep the metric area visible if its metrics are supported. In the case-list area show:

> No matching payment cases were found in the available synthetic dataset for this investigation.

Do not imply that no real customers or payments were affected outside the dataset.

### No search/filter results

Show:

> No cases match your search or selected filters.

Provide **Clear filters** so the engineer can restore the full list.

### Loading

Keep the workspace structure in place and show a restrained loading state in the metrics and case-list areas. Avoid replacing the whole workspace with a blank screen.

### Error loading the thread data

Show:

> We couldn't load the payment-failure investigation data. Try again.

Provide a Retry action. Do not show stale metrics as though they are current unless they are explicitly identified as previously loaded data.

## 7. Responsive and accessibility behaviour

The MVP is desktop-first because the primary persona is an operations engineer working through several evidence sources.

- On wide screens, use the agreed three-column workspace.
- At narrower widths, the thread navigation and AI Assistant may collapse into accessible panels so the center workspace remains usable.
- Keep the Incident Overview information readable when it wraps; do not hide the Synthetic Data indicator.
- On small screens, render each case as a stacked card while preserving the same five fields and full-row interaction.
- Use text labels in addition to status colors.
- Support keyboard navigation, visible focus, and accessible names for search, filters and row actions.

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
- **Overview tab:** thread-level metrics and a list of individual cases.
- **Evidence tab:** source records and traceable relationships for the selected case.
- **Findings tab:** individual claims, AI-proposed statuses and human review decisions.
- **AI Assistant:** persistent, thread-aware conversational support.

The Payment failures Overview should not duplicate detailed evidence or claim review controls. Its main job is to help the engineer understand the pattern and choose which case to inspect next.

## 10. Design completion checklist

- [x] Shared incident header and Synthetic Data indicator.
- [x] Incident time shown with relevant timezone and UTC offset.
- [x] One-line incident description.
- [x] Payment failures thread heading and Overview/Evidence/Findings navigation.
- [x] Compact, source-backed summary metrics with numerator, denominator and time window.
- [x] Individual case list with the five agreed fields.
- [x] Payment status separated from investigation progress.
- [x] Progress derived from human review decisions and scoped to the current revision.
- [x] Search and basic filters with simple defaults.
- [x] Full-row selection opens Evidence with the case selected.
- [x] Assistant remains available with selected-thread context.
- [x] Empty, no-results, loading and error states.
- [x] Desktop-first responsive and accessibility behaviour.
- [x] Explicit MVP exclusions to prevent scope creep.

**Design principle:** The Payment failures Overview gives the engineer a truthful summary of the incident pattern and a clear route into each individual case. It must never confuse a payment outcome with investigation progress or present incomplete evidence as a conclusion.
