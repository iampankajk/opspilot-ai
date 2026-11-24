# OpsPilot AI — Possible Duplicates: Overview Screen Specification v0.1

> **Current scope — 16 November 2026:** D-030–D-034 approve the evidence-first redesign before Task 5B. This screen uses Overview/Evidence without assistant, search/filters, or active Findings. Claim-review-derived progress supersedes evidence-inspection-based progress wording. The [UX Blueprint](UX_BLUEPRINT_V0.1.md) governs shared behavior, implementation increments, measurable UX-R acceptance criteria, and the explicit conflict register. Original examples are illustrative; they do not add records, API fields, or implemented features. Approval is design evidence, not implementation or accessibility verification.

**Phase:** Phase 2 — Screen-level UX Design  
**Screen:** Investigation Workspace → Possible Duplicates → Overview  
**Status:** First-pass design amended by approved evidence-first redesign; implementation pending\
**Depends on:** `PRD_V0.1.md`, `UX_BLUEPRINT_V0.1.md`, and the approved Payment Failures screen specifications

---

## 1. Purpose

The Possible Duplicates Overview helps a Payments Operations Engineer understand the customer reports associated with potential duplicate charges and decide which individual cases to inspect.

It must present reported concerns and available correlation signals without implying that a duplicate charge has been proven.

The screen supports three questions:

1. Which possible-duplicate cases are configured for this thread? The current case count is not a total of complaints or charges.
2. Which individual customer/payment cases need investigation?
3. What available signals may help the engineer decide which case to inspect next?

The screen is an investigation overview, not a payment-resolution or case-management tool.

## 2. Position in the workspace

Select Possible duplicates in the persistent desktop navigation rail, then Overview. Keep the compact shared incident header and Synthetic Data indicator visible. Overview/Evidence are active; Findings is visibly unavailable. No assistant panel. First entry to this thread has no active case; revisiting restores its valid local view/case/evidence UI state within the same loaded page (Blueprint §5).

## 3. Information hierarchy

1. Thread title and concise explanation.
2. Configured-case count, accurately labelled.
3. Compact full list of reported concerns with explicit case selection.

Detailed records belong in Evidence. Aggregate metrics, search/filter controls, findings and human review are outside this redesign.

## 4. Thread introduction

**Title:** Possible duplicates

**Description:** Review customer reports of possible duplicate charges and inspect the related payment attempts and provider evidence.

The wording must use terms such as *reported possible duplicate*, *potential duplicate* or *possible duplicate-charge concern*. Avoid labels such as *duplicate payments* or *confirmed duplicates* unless an individually reviewed finding supports that conclusion.

## 5. Investigation summary metrics — future data-backed capability

Current redesign: show the configured-case count from the implemented contract; omit the aggregate cards below. Their required data/definitions are retained for a later increment and must not be hardcoded from scenario totals, inferred from payload prose, or treated as existing API fields.

### 5.1 Recommended metrics

**A. Possible duplicate-charge reports**

- Count distinct support reports classified in the dataset as possible duplicate-charge concerns.
- The label describes customer reports, not verified duplicate charges.
- For the current tabletop scenario, the supplied incident context describes three possible duplicate-charge complaints. Display that count only when the loaded thread data contains those three distinct reports.

**B. Cases with multiple internal payment attempts**

- Count distinct investigation cases for which available internal payment records show more than one payment attempt associated with the same case/order/customer context.
- A multiple-attempt signal is not proof that multiple charges or captures occurred.
- Do not count raw attempt records as separate cases.

**C. Cases awaiting human review**

- Count distinct cases whose investigation progress is Not started or In progress.
- This is a workflow count, not a payment outcome.
- In the later review feature, a case becomes Reviewed only when all currently linked claims have recorded human decisions (§6.3). Inspection alone never qualifies; Reviewed does not mean a duplicate charge was confirmed or ruled out.

### 5.2 Metric presentation rules

- Each metric must have a clear label and a count.
- A short helper description or tooltip should explain what is counted where confusion is possible.
- Do not display a metric for which the required source data is unavailable or cannot be calculated reliably.
- If a count cannot be calculated, show an unavailable state (for example, `—`) with an explanation rather than displaying zero.
- Do not introduce an aggregate metric named **Confirmed duplicate charges** unless the underlying human-reviewed findings support that exact count.
- Keep the shared incident failure-rate metrics in the Incident Overview or Payment Failures thread; do not repeat them here as though they describe duplicate-charge cases.

## 6. Individual possible-duplicate case list

Below the thread explanation and configured-case count, show the full case list. The aggregate metrics above remain future-only.

Each row represents one customer-reported possible duplicate-charge concern under investigation. It does not represent one payment attempt. A single case may be associated with multiple internal attempts and provider events.

### 6.1 Recommended row information

| Field | Purpose | Example format |
|---|---|---|
| Case reference | Identifies the investigation case | `CASE-…` |
| Customer reference | Helps distinguish the customer context without exposing real identity | `CUST-…` |
| Order/payment reference | Identifies the related order or payment context where available | `ORDER-…` / `PAY-…` |
| Reported amount | Shows the amount the customer says may have been charged more than once | Currency + amount |
| Reported concern | Briefly describes what the customer reported | “Customer reports being charged twice” |
| Investigation progress | Shows the engineer's review progress | Not started / In progress / Reviewed |

Where the data supports it, include a compact **correlation signal** beneath the case details, such as:

- `2 internal payment attempts found`
- `Provider event extract available`
- `Provider evidence coverage not verified`

These are evidence-availability or correlation signals only. They must not be worded as proof of a duplicate charge.

### 6.2 Amount display

- Display the reported amount and currency as supplied by the customer report or approved synthetic case record.
- Do not sum amounts across a case or show a “duplicate amount” unless the data model and evidence explicitly support that calculation.
- If the reported amount is missing or ambiguous, show `Amount not available` rather than deriving it from an unrelated attempt.
- When attempts have different amounts, do not collapse them into one amount; make the discrepancy clear in Evidence.

### 6.3 Investigation progress

The implemented contract returns **Not started**; inspection or future AI generation does not change it. When individual human review is separately implemented, derive progress from claims linked to this case in the active thread/state:

- **Not started:** no linked claim has a recorded human decision, including when there are no linked claims.
- **In progress:** some linked claims have decisions and others await review.
- **Reviewed:** all currently linked claims have decisions.

This replaces the older “started/completed reviewing available evidence” wording. Payment outcome and proposed claim status are separate. A Reviewed case can remain Inconclusive and is not automatically Resolved. A refresh/revision feature is still deferred.

## 7. Case list interactions

### 7.1 Selecting a case

The entire case row is clickable and keyboard accessible.

When selected:

1. Open the Evidence tab.
2. Set the selected case as the active case.
3. Focus the case context; if no valid local response exists, show Not requested/count unknown and Inspect evidence. Selecting the row sends no evidence POST.
4. Keep the case reference and key case context visible in the Evidence screen.
5. Preserve the Possible duplicates thread and case identity; the assistant is deferred.

The selected case must not be presented as a confirmed duplicate simply because the engineer opened it.

### 7.2 Hover and focus

- Show a subtle hover state for pointer users.
- Show a clear keyboard focus indicator.
- Do not rely on color alone to communicate that a row is interactive.

### 7.3 Search and filters — deferred

Show all returned cases without a search field, progress/signal filters, pagination, or sort controls. This supersedes the earlier controls for the current small dataset (D-030).

### 7.4 Ordering and return navigation

Preserve the existing returned case order. Returning to Overview restores list position; revisiting a thread restores its valid local selection. No saved-investigation Home screen or its ordering is introduced. No new ordering API is required.

## 8. Evidence and uncertainty guardrails

Possible-duplicate investigations require particular care because payment attempts, provider events, captures and bank debits are different lifecycle concepts.

The Overview must follow these rules:

1. Two internal payment attempts do not, by themselves, establish two charges.
2. Repeated attempts with the same idempotency key do not, by themselves, prove that only one charge occurred or that no duplicate occurred.
3. A provider authorization or capture event is not the same thing as a verified bank debit or settlement entry.
4. A single capture in an available provider extract does not prove that no other capture or bank debit exists when extract completeness is unverified.
5. A missing provider or bank record in the available dataset must not be described as proof that the event never happened.
6. Temporal proximity or matching amounts alone must not be described as proof of a duplicate.
7. The Overview may summarize observable signals, but evidence interpretation and claim-level status belong in Evidence and Findings.

### Current synthetic scenario caution

The supplied scenario includes a possible-duplicate complaint for which support lookup identifies two internal attempts for the same customer/order/amount and the same idempotency key. The attempts have different internal statuses (timeout and succeeded). The available Stripe extract includes one authorization and one capture, but the extract's completeness is not independently verified, and bank/settlement evidence is not available.

The Overview describes the reported concern and only the fields returned by the current case API. Do not display attempt/provider counts before evidence retrieval merely because this scenario is known from documentation. Evidence may show the returned attempts and limitations after an explicit request. Neither view may state that the customer was charged twice or charged only once without supporting evidence.

## 9. Empty, loading and error states

### 9.1 Loading

- Show a lightweight loading state for the case list and configured-case count; aggregate cards are deferred.
- Keep the shared Incident Overview and workspace navigation available.
- Do not temporarily show zero counts while data is loading.

### 9.2 No possible-duplicate reports

If the selected incident has no reports classified as possible duplicate-charge concerns in the approved dataset, show:

**No possible duplicate-charge reports found**

`There are no reports classified for this investigation thread in the available synthetic dataset.`

Keep the thread navigation and Overview/Evidence/Findings navigation visible. Do not imply that no duplicate charges occurred in the real world.

### 9.3 No search results — not applicable

Search/filters are deferred; no such UI state is required now.

### 9.4 Data retrieval error

Show an error explaining that the case list could not be loaded. Offer explicit retry through the existing operation.

Do not show an empty-state message for a retrieval failure; missing data and failed retrieval are different conditions.

### 9.5 Partial data

If a case exists but some fields or sources are unavailable:

- Keep the case visible.
- Show unavailable values explicitly.
- Do not fill gaps using unrelated payment records.
- Leave detailed source coverage explanations to the Evidence screen, while allowing a concise signal in the case row where useful.

## 10. AI Assistant behaviour — future requirement only

The assistant is deferred from this redesign; there is no right panel, conversation input, or assistant API call. The following constraints are retained only for a later assistant feature.

Within the Possible Duplicates thread, the assistant may use the incident context and the selected thread's available synthetic evidence. If no individual case is selected, it should answer at the thread level. After a case is selected, its working context should focus on that case.

The assistant must:

- Distinguish a customer report from an established payment outcome.
- Distinguish internal attempts from provider authorizations, captures and verified bank debits.
- Explain uncertainty and evidence gaps.
- Cite or link to the relevant records when making evidence-based statements.
- Avoid asserting that a duplicate charge occurred or did not occur without sufficient evidence.

The assistant must not perform refunds, retries, payment changes, customer messaging or external write-back.

## 11. Accessibility and responsive behaviour

- Case rows must be operable by keyboard as well as pointer.
- Case actions and navigation require accessible labels; search/filters are deferred.
- Statuses must use text labels, not color alone.
- Amounts must include currency codes or symbols unambiguously.
- At narrower widths, preserve the case identity, reported amount, and investigation progress; secondary references may move into a supporting line or expandable row content.
- Thread/case navigation uses the Blueprint mobile drawer and preserves valid local context. The assistant is absent at every width. Apply Blueprint responsive/WCAG 2.2 AA verification targets.

## 12. Explicit non-goals

This screen does not:

- Confirm or deny that a duplicate charge occurred.
- Display a bank-debit or settlement conclusion without supporting records.
- Initiate refunds, payment retries, reversals or other payment actions.
- Send messages to customers or support agents.
- Manage a full incident lifecycle or assign cases to a team.
- Provide bulk case review or bulk finding acceptance.
- Introduce production integrations or real customer data.
- Replace the detailed evidence inspection in the Evidence tab or claim review in the Findings tab.

## 13. Acceptance criteria for this screen

For current implementation use Blueprint UX-R01–R08, R15, and R17–R21 as well as these scoped criteria; no item is claimed verified by this document:

1. The screen clearly identifies the Possible Duplicates thread.
2. The configured-case count is labelled correctly; unsupported aggregate metrics are omitted, and reports/attempts are not labelled confirmed charges.
3. Each row represents one customer-reported investigation case, not one payment attempt.
4. The list shows case/customer references, reported amount where available, reported concern and investigation progress.
5. A multiple-attempt signal is clearly distinguished from proof of multiple charges.
6. Selecting a case opens Evidence with that case selected.
7. The full case list appears without search/filters; selecting a case requires explicit action and does not retrieve evidence.
8. Empty, loading, retrieval-error and partial-data states are distinguishable.
9. Local navigation retains the Possible duplicates context without mixing evidence or implying human review; the assistant is absent and Findings unavailable.
10. No payment action or external write-back is exposed from this screen.

## 14. Open details for later design

The following implementation-level details are intentionally not decided here:

- Exact metric card styling and layout dimensions.
- Case references already come from the implemented contract; no format change is part of this redesign.
- Search/filter design only if a later increment reintroduces those controls.
- Exact pagination or list virtualization behaviour, if needed.
- Final responsive breakpoints and visual styling.
- Data schema and how correlation signals are computed.

These details should be settled only when the relevant UX or technical design work requires them. This specification makes no framework, database, API, architecture, model or provider decisions.

---

**Design principle:** Help the engineer identify and inspect reported possible-duplicate cases while making it impossible to mistake a customer report, multiple internal attempts or incomplete provider evidence for proof of a duplicate charge.
