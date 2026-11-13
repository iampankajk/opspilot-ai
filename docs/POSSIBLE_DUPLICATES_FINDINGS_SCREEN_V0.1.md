# OpsPilot AI — Possible Duplicates: Findings Screen v0.1

**Status:** First-pass screen design for product-owner review  
**Phase:** Phase 2 — Screen-level UX Design  
**Parent workflow:** Possible Duplicates investigation thread  
**Related specifications:**
- `docs/UX_BLUEPRINT_V0.1.md`
- `docs/POSSIBLE_DUPLICATES_OVERVIEW_SCREEN_V0.1.md`
- `docs/POSSIBLE_DUPLICATES_EVIDENCE_SCREEN_V0.1.md`
- `docs/PAYMENT_FAILURES_FINDINGS_SCREEN_V0.1.md`

---

## 1. Purpose of this screen

The Possible Duplicates → Findings screen helps a Payments Operations Engineer review what the available evidence does and does not establish about a potential duplicate charge.

The screen must make it easy to distinguish:

- Confirmed facts about internal payment attempts.
- Provider-side authorization and capture events present in the available extract.
- Correlations between records and the basis for those correlations.
- The unresolved question of whether the customer was actually charged more than once.
- AI-proposed claim statuses and the engineer's separate human-reviewed decisions.

The screen supports an evidence-based investigation. It does not determine bank debit or settlement outcomes that are not present in the evidence, and it does not automatically declare a duplicate charge.

## 2. Entry point and workspace context

The engineer reaches this screen by selecting the **Findings** section while the **Possible Duplicates** investigation thread is active.

The workspace retains the agreed overall structure:

- **Incident Overview:** remains visible at the top, including the incident identifier, severity, region, incident date/time with timezone, one-line description when available, and Synthetic Data indicator.
- **Investigation thread sidebar:** Possible Duplicates remains selected.
- **Main workspace:** Findings is the selected section.
- **OpsPilot AI Assistant:** remains available in the right-side panel and follows the Possible Duplicates thread context.

The selected payment case context remains visible on the Findings screen so the engineer knows which customer/order/payment case the claims concern.

### Selected case context

Show the available identifiers and reported amount, for example:

- Case reference: `CASE-003`
- Customer reference: `CUST-208`
- Order reference: `ORD-517`
- Amount: `SGD 48.00`
- Related internal payment attempts: two, where supported by the records

These are illustrative identifiers, not real customer or payment information. Only display fields that exist in the approved synthetic dataset. Do not fabricate missing identifiers.

## 3. Recommended screen hierarchy

The main content should be arranged in this order:

1. Selected case context.
2. A short duplicate-investigation summary that states the current evidence boundary.
3. Claim review controls and review-state filters.
4. Findings grouped by the kind of question they address.
5. A visible evidence-gap / uncertainty summary when relevant.

The AI Assistant remains in the persistent right-side panel. Switching between Overview, Evidence and Findings must not reset the assistant conversation for the selected thread.

## 4. Duplicate-investigation summary

At the top of the main content, show a concise, carefully scoped summary rather than a definitive duplicate-charge verdict.

For the current synthetic scenario, the summary can communicate that:

- Two internal payment attempts are present for the same customer/order/amount context.
- Both attempts use the same idempotency key.
- The internal attempt statuses differ: one is recorded as timed out and the other as succeeded.
- The returned Stripe extract contains one authorization and one capture.
- The extract's completeness has not been independently verified, and bank/settlement evidence is unavailable.
- Therefore, whether the customer was charged twice remains inconclusive from the available evidence.

The screen must not compress these facts into a green/red duplicate verdict. A count of internal attempts is not a count of successful customer charges.

If the evidence changes in another incident or revision, the summary must be generated from that revision's evidence rather than reusing this example's values.

## 5. Findings organization

Group claims by the question they address. This helps the engineer move from internal attempt facts to provider evidence and then to the customer-charge question without treating them as interchangeable.

### 5.1 Internal payment-attempt observations

This group contains claims about what the internal payment records show, such as:

- Two internal payment attempts exist for the same customer/order/amount context.
- The two internal attempts contain the same idempotency key.
- One internal attempt is recorded with a timeout status and the other with a succeeded status.

Each claim must cite the specific internal records that support it. The wording must stay within the source's scope. For example, “the internal attempt is marked succeeded” must not be rewritten as “the customer's bank account was charged.”

### 5.2 Provider-side payment lifecycle evidence

This group contains claims about provider events present in the returned extract, such as:

- The available Stripe extract contains one authorization event.
- The available Stripe extract contains one capture event.

Use explicit scope language such as **“in the returned extract”** or **“among the provider records available to this investigation.”** Do not imply that the extract is complete when completeness has not been verified.

Authorization, capture, settlement and a debit posted to a customer's bank account are different lifecycle concepts. The UI must not treat one as proof of another.

### 5.3 Duplicate-charge assessment

This group addresses the central operational question:

**Does the available evidence establish that the customer was charged more than once?**

For the current synthetic scenario, the proposed status should be **Inconclusive**, because the available evidence does not establish the number of customer bank debits or independently verify the completeness of the provider extract.

The explanation should state what is known, what is missing, and why the available records are insufficient to confirm or rule out a duplicate customer charge.

Do not present “not confirmed” as equivalent to “did not happen.” Do not present the absence of a second record in an incomplete extract as proof that a second charge did not occur.

### 5.4 Evidence gaps and unresolved questions

Show relevant gaps alongside the claims they affect and, where useful, in a compact summary. For the current scenario, relevant limitations include:

- Provider-extract completeness has not been independently verified.
- Bank/settlement evidence is not available in the synthetic evidence package.

Phrase these as limitations of the available investigation evidence. Do not imply that no such records exist in the real world or in systems that were not queried.

## 6. Claim card design

Each claim is displayed as an individual card. The card separates the AI's proposal from the engineer's decision.

Each card contains:

1. **Claim statement:** a concise, testable statement.
2. **AI-proposed status:** Confirmed, Not confirmed or Inconclusive.
3. **AI explanation:** a short rationale that explains how the cited evidence supports the proposed status and identifies important limitations.
4. **Evidence references:** supporting, contradicting and contextual records, with their source labels and record identifiers.
5. **Evidence limitation:** a visible note where missing or incomplete evidence affects the claim.
6. **Human review state:** Awaiting review or Reviewed.
7. **Human-reviewed status:** shown separately after the engineer accepts or corrects the proposal.
8. **Review actions:** Accept proposed status or Correct status, available only while the claim is awaiting review.

Do not merge the AI-proposed status and human-reviewed status into a single badge or field.

### Illustrative claim card

**Claim:** Two internal payment attempts exist for the same customer, order and amount context.

- AI-proposed status: Confirmed
- Explanation: Two distinct internal attempt records are present and share the available customer/order/amount context.
- Supporting evidence: the two internal payment-attempt records.
- Human review: Awaiting review
- Actions: Accept proposed status · Correct status

This example is illustrative. The actual card must cite the exact records and values available in the selected case.

### Illustrative duplicate-charge claim

**Claim:** The available evidence establishes that the customer was charged twice.

- AI-proposed status: Inconclusive
- Explanation: Two internal attempts are present, but the returned provider extract contains one authorization and one capture. The extract's completeness has not been independently verified, and bank/settlement evidence is unavailable. The available records therefore do not establish the number of customer bank debits.
- Supporting/contextual evidence: internal attempt records and returned provider events.
- Evidence limitations: provider-extract completeness not independently verified; no bank/settlement evidence in the available package.
- Human review: Awaiting review
- Actions: Accept proposed status · Correct status

The wording must not imply that the customer was charged twice or that the customer was charged only once.

## 7. Status model

### 7.1 AI-proposed claim status

Use the PRD's three claim statuses:

| Status | Meaning in this screen |
|---|---|
| Confirmed | The available cited evidence supports the claim as written within its stated scope. |
| Not confirmed | The available evidence does not support the claim as written. This does not automatically prove the opposite. |
| Inconclusive | The available evidence is insufficient, incomplete or ambiguous to determine whether the claim is true. |

Use the same wording consistently across both investigation threads. Color must not be the only way to distinguish statuses; include text labels.

### 7.2 Human review state

The review state is separate from the claim status:

- **Awaiting review:** the engineer has not recorded a decision for this claim.
- **Reviewed:** the engineer has accepted the AI-proposed status or corrected it and recorded a human-reviewed status.

“Reviewed” is not a payment outcome and does not mean the customer was refunded, charged, or otherwise made whole.

### 7.3 Human-reviewed status

After a review decision, show the engineer's selected status in a distinct **Human-reviewed status** field. Preserve the original AI-proposed status and explanation so the review history remains traceable.

## 8. Human review interactions

Review happens per claim. There is no bulk accept or bulk correction action.

### 8.1 Accept proposed status

When the engineer selects **Accept proposed status**:

1. Record that the engineer accepted the AI-proposed status.
2. Display the human-reviewed status separately from the AI proposal.
3. Change the claim's human review state to Reviewed.
4. Preserve the claim text, AI proposal, rationale, evidence references and review decision.

Do not describe this action as approval of the entire incident or confirmation of a duplicate charge.

### 8.2 Correct status

When the engineer selects **Correct status**:

1. Open a focused correction interaction within the claim card or a small dialog.
2. Let the engineer choose one of the same three statuses: Confirmed, Not confirmed or Inconclusive.
3. Require a short reason for changing the proposed status, so the correction is understandable later.
4. Save the engineer's chosen status as the human-reviewed status.
5. Preserve the original AI-proposed status and explanation.
6. Change the claim's human review state to Reviewed.

The correction flow must not silently rewrite the original AI proposal.

### 8.3 Changing a reviewed decision

Do not silently overwrite a previously recorded human decision. Any later change must be captured in the investigation's revision/history model, consistent with the PRD's numbered revisions and preservation requirements.

## 9. Evidence references and navigation

Each evidence reference should show enough information to identify it, including:

- Source name.
- Record identifier.
- Timestamp with its source timezone where available.
- Relationship to the claim: supporting, contradicting or contextual.

Selecting an evidence reference should open the Evidence section with the relevant record selected or expanded. The engineer should be able to return to Findings without losing the selected case context.

A record's presence on a claim card must not imply it proves more than its contents support. Explain the correlation basis where the relationship is indirect, such as matching customer/order/amount identifiers or a shared idempotency key.

## 10. Review filters and summary counts

Provide simple filters:

- **All** — all claims for the selected case.
- **Awaiting review** — claims with no recorded human decision.
- **Reviewed** — claims with a recorded human decision.

Counts may accompany the filters, but must be derived from the actual claim review states in the active revision.

Do not add a filter that labels the case as “duplicate confirmed” unless that is explicitly supported by reviewed claims and the product requirements. The screen should avoid turning a collection of claim statuses into an automatic case-level verdict.

## 11. AI Assistant behaviour

The right-side AI Assistant remains available while the engineer reviews findings.

Its working context follows the selected Possible Duplicates thread and selected case. It can explain claims, compare cited evidence, identify missing information, and answer questions about the investigation.

The assistant must:

- Cite the available evidence when making case-specific statements.
- Distinguish internal attempts, provider authorization, provider capture, settlement and customer bank debit.
- State when provider-extract completeness is unknown.
- Avoid claiming that two internal attempts prove two customer charges.
- Avoid claiming that one authorization/capture in an incomplete extract proves there was only one charge.
- Avoid converting an inconclusive claim into a definitive root-cause or duplicate-charge statement.
- Never accept or correct a claim on the engineer's behalf.

Human review actions remain explicit controls owned by the engineer.

## 12. Save and revision behaviour

Claim review decisions are part of the current investigation working state. They do not create a new numbered revision merely because an individual claim is accepted or corrected.

The engineer uses the product's explicit **Save investigation** action to create a new numbered revision, consistent with the PRD.

The saved revision must preserve the evidence snapshot, AI proposals, human-reviewed statuses, correction reasons, relevant annotations, timestamps and evidence references required by the PRD.

The screen should make unsaved changes visible and should not imply that a new revision has been created before the explicit save succeeds.

Previously saved revisions remain read-only. When an older revision is opened, review controls must not suggest that the engineer can modify that historical snapshot.

## 13. Export behaviour

The product's reviewed-summary export may be available from the investigation workspace. When invoked from Findings:

- Human-reviewed claim statuses are included.
- Unreviewed AI proposals are excluded by default, consistent with the PRD.
- If an export option includes unreviewed proposals, those proposals must be explicitly labelled as unreviewed AI suggestions.
- Evidence references and uncertainty limitations must remain traceable in the Markdown output.
- The export must not convert an inconclusive duplicate-charge assessment into a definitive conclusion.

The exact export control placement is a workspace-level detail and is not finalized by this screen specification.

## 14. Empty, loading and error states

### 14.1 No findings available

If no claims have been generated for the selected case, show a clear empty state explaining that no findings are currently available. Do not invent claims to populate the screen.

Where appropriate, the engineer may ask OpsPilot to examine the available evidence. Any resulting claims must still include evidence references and remain awaiting human review.

### 14.2 All claims reviewed

Show that all currently displayed claims have been reviewed, while retaining the distinction between reviewed findings and the unresolved payment outcome. Do not imply that the duplicate-charge question is resolved merely because every claim has a human decision.

### 14.3 Evidence retrieval incomplete

If a source retrieval failed or returned incomplete results, identify the affected source and explain that the available evidence may be incomplete. Do not treat a retrieval failure as evidence that no matching record exists.

### 14.4 No matching evidence

Use wording such as **“No matching records found in the available synthetic dataset.”** Do not use wording that implies no such event or record exists anywhere.

### 14.5 Save failure

If saving a new revision fails, preserve the current working state where possible, show that the revision was not saved, and provide a clear retry path. Do not display a new revision number until the save succeeds.

### 14.6 Read-only historical revision

When a historical revision is open, show a read-only indicator and disable claim review controls. Preserve visibility of the recorded AI and human decisions.

## 15. Accessibility and interaction requirements

- Statuses must include text labels; color alone is insufficient.
- Accept and Correct actions must be keyboard accessible and have clear accessible names.
- Expanded claim details and correction controls must have a logical focus order.
- Evidence references must be keyboard accessible and identify their destination.
- Correction reasons and save errors must be associated with their relevant controls.
- Do not rely on color alone to distinguish supporting, contradicting or contextual evidence.
- Keep claim text and evidence limitations readable without requiring hover.

## 16. Explicit non-goals

This screen does not:

- Declare a duplicate charge solely from multiple internal payment attempts.
- Declare that no duplicate charge occurred because an extract contains one authorization or capture.
- Infer bank debit or settlement from an internal succeeded status or provider capture event.
- Issue refunds, retry payments, change payment state or contact customers.
- Automatically accept, correct or bulk-review claims.
- Determine incident root cause.
- Treat a failed evidence retrieval as proof that an event did not happen.
- Modify a previously saved historical revision.

## 17. First-pass acceptance criteria

The first-pass screen design is considered complete when the following are represented in the UI specification:

1. The selected Possible Duplicates case remains identifiable.
2. Claims are grouped into internal attempt observations, provider lifecycle evidence, duplicate-charge assessment and evidence gaps/unresolved questions.
3. Each claim visibly separates AI-proposed status from human-reviewed status.
4. Claim statuses use Confirmed, Not confirmed and Inconclusive.
5. Each claim links to supporting, contradicting or contextual evidence where available.
6. The duplicate-charge assessment remains Inconclusive for the current synthetic scenario unless stronger evidence is supplied.
7. The UI does not equate internal attempts, authorization, capture, settlement and bank debit.
8. Engineers can accept or correct each claim individually.
9. Corrections preserve the original AI proposal and require a reason.
10. Review state is distinct from payment outcome.
11. Evidence references return the engineer to the relevant Evidence record.
12. The assistant remains available and cannot make human review decisions.
13. Review decisions remain part of the working state until the explicit save creates a new numbered revision.
14. Historical revisions remain read-only.
15. Empty, incomplete retrieval, no-match, save-failure and read-only states are described.

---

## 18. Open design details for later refinement

This is a first-pass screen specification. The following details can be refined during consolidated screen review or visual wireframing:

- Exact visual treatment and spacing of claim groups and cards.
- Whether evidence references appear inline or in a collapsible details region by default.
- The final placement of the workspace-level Save investigation and Export reviewed summary actions.
- Exact copy for individual claim explanations once the final synthetic record identifiers are connected to the screen.
- Responsive behaviour for the persistent AI Assistant on narrower viewports.

These open details do not change the agreed product rules: claim-level human review, traceable evidence, explicit uncertainty, preservation of AI and human decisions, and no unsupported duplicate-charge conclusion.

---

**Design principle:** OpsPilot may help an engineer assess whether evidence supports a possible duplicate charge, but it must never turn two internal attempts or an incomplete provider extract into an unsupported claim about how many times the customer was charged.
