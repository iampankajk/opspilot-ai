# OpsPilot AI — Payment Failures → Findings Screen v0.1

**Status:** First-pass UX design complete; pending product-owner review  
**Phase:** Phase 2 — Screen-level UX Design  
**Parent UX blueprint:** `docs/UX_BLUEPRINT_V0.1.md`  
**Related screens:** `docs/PAYMENT_FAILURES_OVERVIEW_SCREEN_V0.1.md`, `docs/PAYMENT_FAILURES_EVIDENCE_SCREEN_V0.1.md`

---

## 1. Purpose of this screen

The Findings screen helps a Payments Operations Engineer review the claims OpsPilot has proposed from the available evidence and record a human decision for each claim.

The screen must make three things easy to distinguish:

1. **Evidence:** the source records available in the investigation.
2. **AI proposal:** a claim and status proposed by OpsPilot, with an explanation and evidence references.
3. **Human decision:** the status the engineer accepts or chooses instead.

The screen supports evidence-based investigation. It does not automatically determine the incident's root cause, resolve a payment, or take an operational action.

## 2. Placement in the workspace

The Findings screen uses the shared investigation workspace defined in `UX_BLUEPRINT_V0.1.md`:

- **Top:** shared Incident Overview, including the Synthetic Data indicator.
- **Left:** investigation thread navigation.
- **Center:** the selected thread's Findings content.
- **Right:** persistent OpsPilot AI Assistant.

The selected investigation thread is **Payment failures**. The assistant remains available while the engineer navigates between Overview, Evidence and Findings. Its working context follows the selected investigation thread.

The Findings content is thread-level by default. Individual claims may reference one or more payment cases. The engineer should be able to identify the related case without losing the wider incident context.

## 3. Main screen hierarchy

Recommended order within the center workspace:

1. Screen title and short explanation.
2. Compact review summary.
3. Review filters.
4. Claims awaiting human review.
5. Previously reviewed claims.

Claims awaiting review appear first because they represent the next decision the engineer may need to make. Reviewed claims remain accessible so the engineer can understand what has already been decided.

## 4. Screen header

**Title:** Findings  
**Context:** Payment failures  
**Supporting description:** Review what the available evidence supports, what it does not support, and what remains uncertain.

The shared incident metadata remains in the persistent Incident Overview header; it should not be duplicated in this screen's title area.

## 5. Review summary

Show a compact summary of the claims in the selected thread:

- **Total claims:** number of claims currently presented for this investigation thread.
- **Awaiting review:** claims without a recorded human decision.
- **Reviewed:** claims with a recorded human decision.
- **Inconclusive:** claims whose current displayed status is Inconclusive. Make clear whether the count refers to AI proposals or human-reviewed decisions; do not combine the two silently.

The summary is informational. It is not a score, confidence percentage, incident severity, or measure of operational resolution.

Where the two status perspectives differ, show them separately. For example, an AI-proposed Inconclusive status that a human has reviewed and changed to Confirmed must not continue to be counted as a human-reviewed Inconclusive decision.

## 6. Claim card structure

Each claim is presented as an individual card. A card should contain the following information in a consistent order.

### 6.1 Claim statement

A concise, specific statement describing what the available evidence may establish.

Avoid presenting a broad root-cause conclusion when the evidence supports only a narrower observation.

### 6.2 Related case references

Show the relevant case reference or references when known, for example `CASE-001`.

A claim may relate to more than one case. Do not imply a one-to-one relationship unless the evidence supports it.

### 6.3 AI-proposed status

Display one of the three statuses:

- **Confirmed**
- **Not confirmed**
- **Inconclusive**

The label must explicitly say that this is the **AI-proposed status** whenever the claim has not yet been reviewed by a human.

Use short explanatory help text or an accessible tooltip to communicate the intended distinction:

- **Confirmed:** the available evidence supports the claim to the required standard for this investigation.
- **Not confirmed:** the available evidence does not establish the claim. This does not automatically prove the opposite.
- **Inconclusive:** the available evidence is insufficient, incomplete or conflicting, so the claim cannot be determined from the current evidence.

These descriptions must remain consistent with the status definitions in the approved PRD and evidence package. Do not weaken the distinction between Not confirmed and Inconclusive in implementation.

### 6.4 Explanation

Provide a short, plain-language explanation of why OpsPilot proposed the status.

The explanation should identify relevant limitations, conflicting evidence or missing evidence where material. It must not claim that a record proves more than it actually establishes.

### 6.5 Evidence references

Show the source and identifier of the relevant records. Where useful, classify each reference as:

- Supports the claim.
- Contradicts the claim.
- Provides context but does not establish the claim.

The relationship label must be grounded in the evidence. A record's mere presence in the same incident is not enough to call it supporting evidence.

Each reference should be selectable. Selecting it opens the Evidence tab with the corresponding record expanded or highlighted. Preserve the claim context so the engineer can return to the same finding without losing their place.

### 6.6 Review state

The card must clearly show whether it is:

- **Awaiting human review**, or
- **Human reviewed**.

Do not use a single generic “Confirmed” or “Reviewed” badge that hides who made the decision.

## 7. Human review interaction

Every claim is reviewed individually. There is no bulk accept or bulk status-change action.

For an unreviewed claim, provide two primary actions:

1. **Accept proposed status** — records the AI-proposed status as the engineer's human decision.
2. **Correct status** — allows the engineer to select a different status.

### 7.1 Accept proposed status

When the engineer accepts a proposal:

- Record the human decision separately from the AI proposal.
- Mark the claim as Human reviewed.
- Preserve the original AI-proposed status and explanation.
- Show who made the decision only to the extent supported by the product's reviewer-display-name feature; do not imply verified identity.
- Keep the claim and its evidence references available for later inspection.

The UI must not rewrite the AI proposal as though it had originally been the human decision.

### 7.2 Correct status

When the engineer chooses Correct status:

- Present the same three permitted statuses: Confirmed, Not confirmed and Inconclusive.
- Make the available choices clear and mutually exclusive.
- Allow an optional reviewer note explaining the correction.
- Show a final review action before recording the decision if the interaction is more than a single direct selection.
- Preserve both the original AI proposal and the human-selected status.

A human correction is not an instruction to silently alter or delete the underlying evidence or the AI's original proposal.

### 7.3 After review

After a decision is recorded, the card should show two distinct fields:

- **AI proposed:** original status.
- **Human decision:** accepted or corrected status.

For example:

> AI proposed: Inconclusive  
> Human decision: Confirmed  
> Review state: Human reviewed

The actual reviewer name and review timestamp should be shown only when available from the saved review record. The UI must not manufacture identity or timestamps.

A reviewed claim remains visible in the Reviewed section. The decision is preserved in the investigation revision according to the approved save and revision behaviour.

## 8. Example claim cards

The examples below are based on the fictional payment-failure exercise and are illustrative UI content, not real operational findings.

### Example A — A supported observation

**Claim:** The application recorded a timeout while waiting for the payment provider's response.

**AI-proposed status:** Confirmed

**Explanation:** The available application log records a timeout waiting for the provider response. This confirms the recorded timeout observation; it does not establish why the provider response was delayed or what the final payment outcome was.

**Evidence references:**

- `LOG-104` — Application log — Supports the claim.
- `TRACE-204` — Request trace — Provides request context.

**Review state:** Awaiting human review

### Example B — An uncertain possible duplicate

**Claim:** The customer was charged twice for the same order.

**AI-proposed status:** Inconclusive

**Explanation:** The available internal records show two payment attempts with the same idempotency key, while the returned provider extract shows one authorization and one capture. The extract's completeness is not independently verified, and bank or settlement evidence is not available. The current evidence is insufficient to determine whether the customer experienced two separate charges.

**Evidence references:**

- Internal payment lookup — Provides two-attempt context.
- Provider event extract — Shows the returned authorization and capture records.
- Missing bank or settlement evidence — A stated limitation, not a record proving no second debit occurred.

**Review state:** Awaiting human review

This example demonstrates why OpsPilot must not turn two internal attempts into a conclusion that two customer charges occurred.

## 9. Filters and navigation within Findings

Keep filtering lightweight for the MVP. Recommended filters:

- **All claims**
- **Awaiting review**
- **Reviewed**

Optionally allow filtering by the three claim statuses when the number of claims makes that useful. Do not add complex search, sorting, saved views or analytics for the synthetic MVP unless testing shows a clear need.

The default view should prioritize Awaiting review while keeping the Reviewed section accessible below it. The user can select All claims to see both groups together.

## 10. Empty and exceptional states

### 10.1 No claims proposed yet

Message:

> No findings have been proposed for this investigation yet.

Supporting text:

> Findings will appear here when OpsPilot has analyzed the available evidence. You can continue inspecting evidence or ask the assistant a question.

Do not fabricate placeholder claims or display zero-value findings as if an investigation has already occurred.

### 10.2 No claims match the selected filter

Message:

> No claims match this filter.

Provide a simple way to return to All claims.

### 10.3 Loading

Use a restrained loading state in the claims area. Keep the shared incident header, thread navigation and assistant shell stable where possible.

### 10.4 Findings unavailable

Message:

> Findings could not be loaded.

Offer a retry action. Do not show an empty state when the actual problem is a retrieval or loading failure.

### 10.5 Evidence reference unavailable

If a referenced record cannot be opened, preserve the claim card and explain that the evidence record is currently unavailable. Do not remove the reference or imply that the evidence never existed.

### 10.6 Review could not be saved

If recording a human decision fails:

- Clearly state that the decision was not saved.
- Keep the proposed and selected statuses visible.
- Do not mark the claim as Human reviewed until persistence succeeds.
- Let the engineer retry without silently discarding the selection or note.

## 11. AI Assistant behaviour on this screen

The assistant remains visible in the right-side panel and follows the Payment failures thread context.

The engineer may ask questions about:

- Why a particular status was proposed.
- Which evidence supports or contradicts a claim.
- What information is missing.
- What additional evidence would help distinguish competing explanations.

The assistant may explain or propose a revised claim for human consideration, but it must not silently change a claim's human-reviewed status or record a human decision.

Any newly proposed or revised claim must remain visibly an AI proposal until an engineer reviews it individually.

## 12. Navigation and context preservation

- Switching between Overview, Evidence and Findings keeps the selected investigation thread.
- The assistant remains available and keeps the thread context while switching among these sections.
- Selecting an evidence reference opens the Evidence tab focused on that record.
- Returning to Findings should restore the engineer's previous place and selected claim where practical.
- Switching to another investigation thread changes the assistant's working context and displayed findings to that thread.
- Shared incident context remains available across both threads.

## 13. Trust, safety and scope constraints

The Findings screen must:

1. Keep AI proposals separate from human decisions.
2. Require individual human review for every claim.
3. Preserve original AI proposals when a human accepts or corrects them.
4. Link claims to traceable evidence references.
5. Distinguish support, contradiction, context and missing evidence.
6. Show uncertainty rather than forcing a conclusion.
7. Avoid treating a timeout as a root cause.
8. Avoid treating two payment attempts as proof of two customer charges.
9. Avoid treating a provider extract as complete unless completeness is established.
10. Avoid implying that Not confirmed proves the opposite claim.
11. Avoid bulk acceptance or automatic human approval.
12. Avoid payment operations, refunds, retries, customer messaging or production write actions.
13. Keep synthetic records clearly identified as synthetic through the shared Incident Overview indicator.

## 14. Relationship to investigation progress

The Overview screen displays a separate Investigation Progress value for each payment case. That value must not be confused with payment status or claim status.

For the first-pass UX, the progress labels remain:

- **Not started**
- **In progress**
- **Reviewed**

They should be derived from the human review state of the claims associated with that case, not from payment outcome and not merely from opening the case:

- Not started: no associated claim has a recorded human review decision.
- In progress: at least one associated claim has been reviewed, but other associated claims remain awaiting review.
- Reviewed: all currently associated claims have a recorded human review decision.

Reviewed means the currently available claims for that case have been reviewed. It does not mean the payment was resolved, the root cause was found, or the customer was made whole.

If a case has no associated claims yet, keep it Not started rather than inferring progress.

## 15. Accessibility and interaction guidance

- Status must be communicated with text, not colour alone.
- Buttons must have clear action labels such as Accept proposed status and Correct status.
- Claim cards and evidence references must be keyboard accessible.
- Focus should return to the originating claim after an engineer inspects an evidence reference and navigates back.
- Review state and AI-versus-human distinction must be understandable to assistive technologies.
- Do not use colour as the only indication of supporting or contradicting evidence.

## 16. Explicitly out of scope for this screen

- Bulk accept, bulk correction or automated approval.
- Automatic root-cause declaration.
- Payment retries, refunds or other payment actions.
- Customer communication or support-ticket write-back.
- Production system write actions.
- Multi-incident analytics or organization-wide reporting.
- Complex claim assignment, collaboration or approval chains.
- Editing source evidence from the Findings screen.

## 17. Open implementation details

The following are intentionally not decided by this UX specification:

- Exact component library or frontend implementation.
- Backend data model and API contracts.
- LLM, agent framework or model-provider choices.
- Database, infrastructure and authentication design.
- Exact persistence mechanics beyond the approved save and revision requirements.
- Final visual styling, spacing and responsive breakpoints.

These decisions should be made only when the project reaches the relevant technical design or implementation stage.

---

## 18. Screen completion checklist

- [x] Findings are presented as individual claims.
- [x] AI-proposed statuses are visually distinct from human decisions.
- [x] Claims include plain-language explanations and evidence references.
- [x] Supporting, contradicting, contextual and missing evidence are differentiated.
- [x] Each claim has individual Accept and Correct review actions.
- [x] No bulk review action is included.
- [x] Original AI proposals are preserved after human review.
- [x] Evidence references navigate to the relevant Evidence record.
- [x] Loading, empty, unavailable and save-failure states are defined.
- [x] Investigation progress remains distinct from payment and claim status.
- [x] The screen preserves thread-aware assistant context.
- [x] Synthetic-data context remains visible through the shared incident header.
- [x] No production write actions or payment operations are introduced.

**Design principle:** Findings should make it clear what OpsPilot proposes, why it proposes it, what evidence is available, and what the engineer has personally decided—without allowing an AI suggestion to masquerade as a human-reviewed conclusion.
