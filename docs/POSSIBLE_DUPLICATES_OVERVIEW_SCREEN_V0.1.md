# OpsPilot AI — Possible Duplicates: Overview Screen Specification v0.1

**Phase:** Phase 2 — Screen-level UX Design  
**Screen:** Investigation Workspace → Possible Duplicates → Overview  
**Status:** First-pass design for product-owner review  
**Depends on:** `PRD_V0.1.md`, `UX_BLUEPRINT_V0.1.md`, and the approved Payment Failures screen specifications

---

## 1. Purpose

The Possible Duplicates Overview helps a Payments Operations Engineer understand the customer reports associated with potential duplicate charges and decide which individual cases to inspect.

It must present reported concerns and available correlation signals without implying that a duplicate charge has been proven.

The screen supports three questions:

1. How many possible duplicate-charge concerns have been reported?
2. Which individual customer/payment cases need investigation?
3. What available signals may help the engineer decide which case to inspect next?

The screen is an investigation overview, not a payment-resolution or case-management tool.

## 2. Position in the workspace

The screen appears when the engineer selects **Possible duplicates** in the left investigation-thread navigation and then selects **Overview** in the main workspace.

It uses the shared workspace shell already defined in `UX_BLUEPRINT_V0.1.md`:

- Incident Overview remains visible at the top.
- Investigation Threads remain in the left sidebar.
- Overview, Evidence and Findings remain the center workspace sections.
- OpsPilot AI remains available in the right-side panel.

The AI assistant follows the Possible Duplicates thread context. Moving between Overview, Evidence and Findings does not reset the conversation. The assistant must not silently mix in Payment Failures thread-specific evidence or conclusions.

## 3. Information hierarchy

The center workspace should present content in this order:

1. Thread title and short explanation.
2. Compact investigation summary metrics.
3. Individual possible-duplicate cases.
4. Search and filters for locating a case.

The screen should remain focused on identifying and opening a case. Detailed payment records belong in Evidence; claim-level conclusions and human review belong in Findings.

## 4. Thread introduction

**Title:** Possible duplicates

**Description:** Review customer reports of possible duplicate charges and inspect the related payment attempts and provider evidence.

The wording must use terms such as *reported possible duplicate*, *potential duplicate* or *possible duplicate-charge concern*. Avoid labels such as *duplicate payments* or *confirmed duplicates* unless an individually reviewed finding supports that conclusion.

## 5. Investigation summary metrics

Show a compact row of up to three metrics above the case list. Metrics are calculated from the currently selected incident's Possible Duplicates thread and its available synthetic dataset.

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
- A case becomes Reviewed only when the engineer has reviewed the available evidence for that case. Reviewed does not mean a duplicate charge was confirmed or ruled out.

### 5.2 Metric presentation rules

- Each metric must have a clear label and a count.
- A short helper description or tooltip should explain what is counted where confusion is possible.
- Do not display a metric for which the required source data is unavailable or cannot be calculated reliably.
- If a count cannot be calculated, show an unavailable state (for example, `—`) with an explanation rather than displaying zero.
- Do not introduce an aggregate metric named **Confirmed duplicate charges** unless the underlying human-reviewed findings support that exact count.
- Keep the shared incident failure-rate metrics in the Incident Overview or Payment Failures thread; do not repeat them here as though they describe duplicate-charge cases.

## 6. Individual possible-duplicate case list

Below the summary metrics, show the individual reported concerns as a case list.

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

Use the same three investigation-progress values as the Payment Failures Overview:

- **Not started** — no case-level evidence review has been recorded by the engineer.
- **In progress** — the engineer has started reviewing this case but has not completed the review of its available evidence.
- **Reviewed** — the engineer has completed a review of the currently available evidence for this case.

Investigation progress is distinct from payment state and from the finding status values Confirmed, Not confirmed and Inconclusive.

A Reviewed case may still have Inconclusive findings. Do not label a case Resolved solely because its investigation progress is Reviewed.

## 7. Case list interactions

### 7.1 Selecting a case

The entire case row is clickable and keyboard accessible.

When selected:

1. Open the Evidence tab.
2. Set the selected case as the active case.
3. Focus the evidence view on records associated with that case.
4. Keep the case reference and key case context visible in the Evidence screen.
5. Preserve the Possible Duplicates thread context in the AI assistant.

The selected case must not be presented as a confirmed duplicate simply because the engineer opened it.

### 7.2 Hover and focus

- Show a subtle hover state for pointer users.
- Show a clear keyboard focus indicator.
- Do not rely on color alone to communicate that a row is interactive.

### 7.3 Search

Provide a search field above the list. Search only fields available in the synthetic case data, such as:

- Case reference
- Customer reference
- Order reference
- Payment reference
- Support-ticket reference

Search must not silently search free-form hidden evidence or unrelated incident threads.

### 7.4 Filters

Provide a compact **Investigation progress** filter:

- All cases
- Not started
- In progress
- Reviewed

Optionally provide a **Correlation signals** filter only if the synthetic dataset has structured, consistently defined signal fields. Do not infer a signal from unstructured text at display time.

### 7.5 Default ordering

Order cases by most recently reported first when a reliable report timestamp is available. If report timestamps are unavailable, use a stable deterministic order and do not imply recency.

Do not apply the Home screen's “most recently saved incident first” rule to this list; that rule applies to saved investigations on the Home screen.

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

The Overview must therefore describe this as a reported concern with multiple internal attempts and incomplete/unverified downstream evidence. It must not state that the customer was charged twice or that the customer was charged only once.

## 9. Empty, loading and error states

### 9.1 Loading

- Show a lightweight loading state for summary metrics and case rows.
- Keep the shared Incident Overview and workspace navigation available.
- Do not temporarily show zero counts while data is loading.

### 9.2 No possible-duplicate reports

If the selected incident has no reports classified as possible duplicate-charge concerns in the approved dataset, show:

**No possible duplicate-charge reports found**

`There are no reports classified for this investigation thread in the available synthetic dataset.`

Keep the thread navigation and Overview/Evidence/Findings navigation visible. Do not imply that no duplicate charges occurred in the real world.

### 9.3 No search results

Show:

**No matching cases**

`Try another case, customer, order, payment or ticket reference, or clear the current filters.`

Provide a clear action to reset search and filters.

### 9.4 Data retrieval error

Show an error explaining that the case list or summary metrics could not be loaded. Offer retry where supported.

Do not show an empty-state message for a retrieval failure; missing data and failed retrieval are different conditions.

### 9.5 Partial data

If a case exists but some fields or sources are unavailable:

- Keep the case visible.
- Show unavailable values explicitly.
- Do not fill gaps using unrelated payment records.
- Leave detailed source coverage explanations to the Evidence screen, while allowing a concise signal in the case row where useful.

## 10. AI Assistant behaviour

The right-side assistant remains available while the engineer uses the Overview tab.

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
- Search and filter controls must have accessible labels.
- Statuses must use text labels, not color alone.
- Amounts must include currency codes or symbols unambiguously.
- At narrower widths, preserve the case identity, reported amount, and investigation progress; secondary references may move into a supporting line or expandable row content.
- The right-side AI panel may collapse according to the shared workspace responsive behaviour, without changing the selected thread or case.

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

The first-pass design is satisfied when:

1. The screen clearly identifies the Possible Duplicates thread.
2. Summary metrics use explicit definitions and do not label reports or attempts as confirmed duplicate charges.
3. Each row represents one customer-reported investigation case, not one payment attempt.
4. The list shows case/customer references, reported amount where available, reported concern and investigation progress.
5. A multiple-attempt signal is clearly distinguished from proof of multiple charges.
6. Selecting a case opens Evidence with that case selected.
7. Search and progress filters operate only on fields and statuses supported by the case data.
8. Empty, loading, retrieval-error and partial-data states are distinguishable.
9. The AI assistant retains the Possible Duplicates thread context and avoids unsupported payment conclusions.
10. No payment action or external write-back is exposed from this screen.

## 14. Open details for later design

The following implementation-level details are intentionally not decided here:

- Exact metric card styling and layout dimensions.
- Final case reference format.
- Exact search implementation and filter-control design.
- Exact pagination or list virtualization behaviour, if needed.
- Final responsive breakpoints and visual styling.
- Data schema and how correlation signals are computed.

These details should be settled only when the relevant UX or technical design work requires them. This specification makes no framework, database, API, architecture, model or provider decisions.

---

**Design principle:** Help the engineer identify and inspect reported possible-duplicate cases while making it impossible to mistake a customer report, multiple internal attempts or incomplete provider evidence for proof of a duplicate charge.
