# OpsPilot AI — Human Findings Review MVP PRD

**Status:** Product discovery finalized; ready for technical feasibility and UX design\
**Version:** 1.0 (27 November 2026)\
**Product:** OpsPilot AI (fictional payment-incident investigation assistant)\
**Feature:** Human Findings Review\
**Primary user:** Payments Operations Engineer\
**Final approver:** Payments Lead / Incident Commander\
**Scope:** Review and governance of AI-generated incident findings; not authorization or execution of customer financial remediation

## 1. Executive summary

OpsPilot AI can generate evidence-backed draft findings from synthetic payment-incident data and persist their citations. Its demonstrated Gemini generation produced five findings and five proposals with nine evidence citations; these findings were left `awaiting_review`. The MVP adds a human-in-the-loop experience to inspect evidence, validate or challenge conclusions, propose corrections, track revisions, and obtain final independent Lead approval. It must preserve source provenance, past decisions, and an auditable record without treating AI-generated claims as automatically authoritative.

**Outcome sought:** A Payments Operations Engineer can take a generated finding through evidence validation to a traceable Payments Lead decision, including correction, re-investigation and versioning when necessary.

## 2. Problem and user needs

**Problem:** A generated finding is not an operationally approved conclusion. Without a review workflow, engineers cannot consistently verify that claims match source evidence, Lead accountability is unclear, revised findings can obscure prior conclusions, and impact categorization may be unreliable.

**Primary user — Payments Operations Engineer:** Needs to compare a claim with citations, inspect source records, mark evidence sufficiently supported or not, request more investigation, propose traceable corrections, and submit validated revisions to the Lead.

**Secondary user — Payments Lead / Incident Commander:** Needs a queue of only validated current revisions, clear evidence and risk rationale, options to approve, return for correction or permanently reject, and reliable audit trails. The Lead is independent from the engineer for final approval.

## 3. Goals and non-goals

### MVP goals
1. Render draft findings within their investigation with clear current revision, AI/human provenance, risk classification, evidence citations and state.
2. Support engineer validation, requests for further investigation, rejection as unsupported, and human-proposed corrections.
3. Support both manual investigation and existing AI-assisted investigation capabilities where feasible, with explicit user initiation, budget controls and re-review.
4. Enforce Lead-only final approval after validation; allow individual review and optional guarded bulk approval.
5. Preserve immutable original AI outputs, revisions, evidence references, decisions and actor/timestamp/reason trails.
6. Classify findings' impact with deterministic rules and explicit human confirmation/override.

### Non-goals for this MVP
- Automatically executing refunds, chargebacks, rollbacks, failovers, changes to payment-provider configuration or other remediation.
- Sending customer communications or closing refund reconciliation.
- Treating proposed AI root cause or risk label as verified without human review.
- Building a general-purpose incident command center, advanced reviewer staffing/scheduling, or arbitrary workflow customization.
- New live provider integrations; use existing synthetic evidence and implemented generation pathways.
- Automatically regenerating AI findings in background or burning API quota during QA.

## 4. Decisions finalized

### Previously agreed (Decisions 1–22)
1. Two-stage approval: engineer validates evidence; a Payments Lead / Incident Commander independently makes the final decision.
2. Individual Lead approval/rejection by default; optional bulk approval of eligible validated findings.
3. Engineer can request further investigation or reject evidence validation if a claim is unsupported.
4. Further investigation may be manual or explicitly AI-assisted; updated findings return to engineer validation.
5. Findings have stable logical identity and immutable, retained revisions with their evidence, AI output and review history.
6. An approved earlier revision becomes `superseded` if a later revision is created; its historical approval remains in audit records. A new revision requires fresh validation and Lead approval.
7. Engineer proposes corrections as traceable revisions; original AI output is never overwritten.
8. An engineer may validate their own proposed correction. Only the Lead may grant final approval.
9. Lead can return a finding for correction or permanently reject it; a reason is mandatory for either action.
10. Written Lead approval rationale is mandatory for high-impact findings, optional for routine findings. Every decision is audited.
11. Impact uses financial risk, customer impact, incident severity and evidence uncertainty. A serious concern in any dimension can trigger high impact.
12. System proposes classification, engineer verifies/recommends adjustment, Lead confirms. Overrides require written reason and audit entry.
13. Classification uses configurable explicit thresholds and critical-risk triggers plus documented human exception handling.
14. Five critical-risk trigger categories: suspected duplicate charges/captures; confirmed or suspected significant financial loss; unresolved material customer financial remediation; critical payment-service disruption; and high uncertainty with serious potential consequences. These categories need evidence-based qualifiers and must not fire for uncorroborated weak signals or trivial routine events.
15. Customer impact threshold: **>=100 distinct affected customers**, not attempts; unknown must not be counted as zero.
16. Financial exposure threshold: **>=USD 10,000 reasonably estimated exposure**; record estimated exposure separately from confirmed loss; avoid double counting retries. This is a configurable fictional-platform assumption.
17. Absolute failure rule: **>=20% failed eligible payment attempts** over a rolling 15-minute window.
18. Absolute failure rule minimum denominator: **>=100 eligible attempts** in the same 15-minute window; low-volume incidents remain eligible for other escalation routes.
19. An independent baseline deterioration trigger is allowed in addition to the absolute failure rule.
20. Baseline deterioration thresholds: current failure rate **>=3x** the reliable historical baseline **and >=5 percentage points higher** than baseline; configurable assumptions.
21. Baseline: matching 15-minute periods from the previous four weeks by payment provider, region, weekday and local time of day; known incident windows excluded. Derive the baseline from total failures / total eligible attempts across qualifying windows (volume weighted).
22. At least **3 of 4** matched historical windows must pass sufficiency and data-quality checks before the baseline rule is available.

### Remaining choices finalized here by delegated recommendation (Decisions 23–30)
23. **Historical window minimum traffic:** Each qualifying historical 15-minute window requires **>=100 eligible attempts**. A current baseline-comparison window must also contain >=100 attempts; otherwise this rule is unavailable. Separate critical-risk triggers may still escalate.
24. **Data quality and unknown state:** Exclude incident-tagged, duplicate/overlapping, incomplete, misattributed, or materially delayed telemetry windows. Compute only from comparable eligible attempts. Display `insufficient_data` or `unavailable` (not `routine`) when baseline prerequisites fail; show which prerequisite failed. The absolute rule remains independently evaluable.
25. **Baseline math and reliability:** Use UTC timestamps for storage and an explicit provider-region reporting timezone for matching weekday/time. Exclude current incident windows and known contaminated historical windows. If baseline is zero, the relative 3x test is satisfied mathematically for a positive current rate, but the >=5 percentage-point increase and both traffic/quality safeguards still apply. Never divide by zero. Round only for display, not classification.
26. **Risk rules are transparent and configurable:** Implement rules as versioned configuration/defaults, with outcome + reasons + evidence/source references + rule version visible. Missing or conflicting risk data results in `needs_assessment` and human attention, not silent low risk. Suggested system classification is not a final decision.
27. **Conservative treatment of downgrades:** An engineer may recommend a change but cannot finalize classification. Lead-confirmed overrides require a recorded reason. A finding initially flagged high impact (by any critical trigger or threshold) must still have a written Lead approval justification even if subsequently downgraded; prior classification and reason remain visible.
28. **Correction/revision semantics:** Each edit that changes claim, rationale or citation evidence creates a new immutable revision with creator, change reason, source `AI` or `human_corrected`, linked parent revision and evidence snapshot/reference set. Earlier validation and approval never transfer to the new revision. An engineer can revise their own proposed correction; a permanently rejected logical finding cannot be resubmitted as another revision. Distinct genuinely new findings can be created only through normal investigation workflows, not as a rejection bypass.
29. **Bulk approval safeguards:** Only current, engineer-validated, non-superseded revisions eligible for the same authorized Lead can be selected. Each approved revision receives an individual audit event. A shared bulk justification may be applied only if explicitly associated with every included high-impact finding; the UI must show which findings it covers. Conflicts, stale revisions, missing mandatory rationale or missing authorization block the affected items. No partial success should be hidden: clearly report per-item outcome.
30. **Authentication, audit and safety:** Derive actor identity and role server-side, enforce authorizations on APIs (not only UI), and forbid an engineer from final approving even their own corrected finding. Require reason on return, permanent rejection and overrides. Preserve append-only decision history with action, identity, timestamp, prior/new state, revision ID and reason. No automatic remediation or provider call upon approval.

**These are agreed MVP policy defaults, not regulatory or industry-standard thresholds.** Technical design may expose feasibility constraints for explicit product change control; never silently weaken a safeguard.

## 5. Proposed user journeys

### Journey A — Standard review
1. Engineer opens investigation → AI-generated findings list; each entry shows status, impact recommendation, provenance, latest revision and evidence count.
2. Engineer opens finding → examines claim, rationale, proposed impact, cited evidence snippets and source-record navigation.
3. Engineer verifies supporting citations and either validates the current revision or takes an alternate action.
4. Validated revision enters Lead queue. Lead independently views evidence, confirms impact classification and explicitly approves (with rationale if high impact) or takes an alternate action.
5. Approval remains a recorded finding decision; it does not trigger financial remediation.

### Journey B — Insufficient evidence
1. Engineer chooses `request further investigation`, records a reason and selects manual or explicitly AI-assisted follow-up.
2. Additional evidence/correction produces a new revision where conclusions or supporting evidence change; earlier material remains accessible.
3. Engineer validates the revised evidence again before Lead review.
4. Engineer may instead mark the current finding unsupported (`validation_rejected`); it must not enter the Lead queue.

### Journey C — Human correction
1. Engineer identifies an overclaim; opens `propose correction`, enters revised text/citations and a required reason.
2. New human-corrected revision is created while original AI generation remains immutable.
3. Same engineer may validate it; independent Lead approval remains mandatory.

### Journey D — Lead disagreement
1. Lead returns a validated finding for correction with reason, permitting a fresh revision/revalidation; **or** permanently rejects with reason.
2. Permanent rejection closes that logical finding for resubmission; preserve complete audit history.

### Journey E — Revision after approval
1. New evidence motivates a new revision of an approved finding.
2. Earlier approved revision retains its historical approval but is marked superseded, not currently approved.
3. New current revision begins without transferred human validation or approval.

## 6. Lifecycle and state semantics

Use an explicit revision lifecycle in the technical design. Suggested domain labels (not yet confirmed DB/API enum values):

`awaiting_engineer_review` → `awaiting_lead_review` → `approved`

Engineer alternatives: `needs_further_investigation`, `validation_rejected`. Lead alternatives: `returned_for_correction`, `permanently_rejected`. A new revision resets to `awaiting_engineer_review`. Mark prior revisions `superseded` as a **version property**, preserving their historical decision.

**Existing system compatibility:** The current demonstrated generated-finding state is `awaiting_review`. Engineering must map or migrate states without assuming the above proposed labels already exist. Define how existing findings/proposals and draft-version records map to one logical finding and its revisions before choosing schema/API representation.

**Invariants:** Only the latest active revision can be approved; the Lead cannot approve unvalidated findings; revision changes invalidate that revision's pending decisions; decisions must target exact revision identifiers to prevent stale-action approval; permanent rejection is terminal for the logical finding; historical events are never deleted.

## 7. MVP functional requirements and acceptance criteria

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-01 | Findings overview | User sees findings in an investigation, current status/revision, classification and pending reviewer stage; empty/loading/error states exist. |
| FR-02 | Evidence inspection | Citations navigate to attributable evidence records/paths; broken or missing citation is clearly flagged and cannot be silently represented as validated evidence. |
| FR-03 | Engineer decisions | Authorized Engineer can validate, request more investigation or reject validation with required reasons for non-validation; invalid transitions are blocked server-side. |
| FR-04 | Corrections | New immutable revision retains original AI output and change reason; authored content clearly marked human-corrected; prior review does not transfer. |
| FR-05 | Lead queue | Contains only eligible engineer-validated current revisions; Lead can inspect all context and confirm classification. |
| FR-06 | Lead decisions | Authorized Lead can approve, return, permanently reject with appropriate reason requirements; explicit final approval recorded. |
| FR-07 | Bulk approval | Validated current revisions only; mandatory impact rationales enforced per finding; results/audit per finding; no stale action silently succeeds. |
| FR-08 | Revision history | Viewer can inspect original AI output, past versions, evidence sources, correction reasons, historical approvals and supersession. |
| FR-09 | Impact engine | Evaluate the five critical-risk categories and numeric thresholds; return rule hits, configuration version and data-quality status. |
| FR-10 | Human impact review | Engineer recommends; Lead confirms or overrides with reason; high-impact origin can't bypass approval rationale through downgrade. |
| FR-11 | Permissions | API authorizes identity/role; Engineer cannot final approve; unauthenticated/unauthorized decisions denied. |
| FR-12 | Audit | Immutable events record actor, role, timestamp, revision, decision, reason and before/after; replayable decision history. |
| FR-13 | AI/manual follow-up | Manual attachment/annotation with source provenance; optional explicitly triggered AI follow-up honors current provider limits; no automatic background provider calls. |
| FR-14 | Failure and concurrency safety | Stale revision updates return an actionable conflict; no duplicate approvals from retries; transactional persistence where required; clear recovery/error UI. |

### Example acceptance scenarios
- Given 5 generated findings, when an Engineer validates 3, only those 3 **current revisions** appear in Lead's eligible queue.
- Given a validated finding is revised, when Lead attempts to approve the old revision, the API rejects the stale decision.
- Given an approved finding gets a new revision, old approval is visible as historical, and new revision is unvalidated.
- Given a high-impact finding is downgraded with a reason, when Lead approves it, written approval rationale is still required.
- Given 2 failures among 10 attempts, the 20% absolute trigger does not fire because denominator is below 100; no conclusion of routine safety is inferred.
- Given current failure rate 8%, historical baseline 2%, >=100 current attempts and >=3 valid baseline windows, the relative and +5pp tests pass; details and evidence are shown.
- Given insufficient historical windows, baseline rule is unavailable (not false/equivalent to safe); independent thresholds still evaluate.
- Given Lead returns or permanently rejects a finding, a missing reason blocks the decision.
- Given correction submitted by Engineer A and validated by Engineer A, final approval remains restricted to an authorized Lead.

## 8. UX requirements

**Investigation Findings tab:** findings count, current status, risk badge and *why*, author/provenance, revision, reviewer stage; filters for awaiting engineer, awaiting Lead, returned, approved and permanently rejected.

**Finding detail:** claim, rationale, evidence citations with source navigation, confidence/uncertainty where actually available, impact explanation, latest/previous revisions, timestamps, action controls. Do not fabricate model confidence where not returned.

**Engineer actions:** validate evidence, request further investigation (reason + manual/AI route), reject validation (reason), propose correction (diff-style comparison + mandatory reason).

**Lead actions:** approve, return for correction, permanently reject, confirm/override classification, bulk-approve eligible selections with justification checks.

**History view:** immutable timeline, revision comparison, source and actor attribution, superseded versus current, events tied to exact revision.

**Safety and accessibility:** clear distinguishing labels for AI generated vs human corrected, confirmation for permanent rejection, keyboard accessible evidence navigation and dialogs, understandable errors, no misleading “final” status on stale data.

## 9. Data and API expectations (contracts to design, not assumed implemented)

Entities/records should represent: investigation, logical finding ID, immutable finding revision, source citations/evidence snapshot references, review decision/event, impact assessment (proposed/engineer/Lead confirmed), ruleset version, actor, timestamps and reasons.

APIs must allow listing and reading findings and revisions, validating/requesting follow-up/rejecting evidence, creating corrected revisions, confirming impact, Lead actions and guarded bulk approvals, and fetching audit history. Decisions should carry an expected revision ID/version for optimistic concurrency. Server must enforce roles, prerequisites and idempotency.

**Repository assessment required before implementation:** inventory existing finding schemas, citation pointer contracts, draft generation states, authentication/roles and available UI. Adapt or extend existing contracts without duplicating their persistence model. Role/auth model must be implemented or explicitly scoped if today's system only has visitor sessions.

## 10. Nonfunctional requirements

- **Correctness:** Reject invalid or missing citation references; no unsupported approval transitions; durable atomic persistence for each decision.
- **Auditability:** Append-only decision history with provenance; revisions visible even when superseded.
- **Security:** Secure role-based server authorization; no trusting client-side role claims; local HTTP dev mode never relaxes production transport requirements.
- **Reliability:** Idempotent commands and optimistic locking for concurrent reviewers; no partial hidden outcomes in bulk operations.
- **Privacy:** Synthetic datasets and no unnecessary sensitive payment data in UI, logs or test fixtures.
- **Testability:** Deterministic fixture-driven tests for risk and workflow transitions; mock AI provider, no automatic live Gemini/OpenAI calls.
- **Performance/accessibility:** Paginated findings as needed, responsive evidence navigation, keyboard and screen-reader semantics.

## 11. Risks and unresolved engineering validations

These are **not additional product-choice questions**, but implementation feasibility checks:

1. Existing backend uses `awaiting_review`; define compatible review and revision state model, migration and link to existing findings/proposals.
2. Establish how separate Engineer vs Lead roles are authenticated and tested; visitor-cookie identity alone may not prove organization-level permissions.
3. Validate synthetic dataset actually provides enough clean historical telemetry and customer identifiers for all thresholds; if not, add deterministic synthetic fixtures explicitly rather than imply real coverage.
4. Define exact eligibility, event correlation and duplicate-payment qualifiers using existing evidence definitions; unknown or uncertain evidence must not be presented as confirmed.
5. Decide technical representation of `validation_rejected`, `permanently_rejected` and `superseded` so audit views and query filters are consistent.
6. Ensure an approved finding's later supersession does not silently reverse or execute external financial actions.
7. Keep current local HTTP support and any generated `frontend/next-env.d.ts` change out of unrelated feature commits unless explicitly approved.

## 12. Success criteria and validation plan

**MVP release gate** (all required):
- A synthetic investigation can be followed end to end: generated finding → evidence inspection → Engineer validation → Lead decision.
- Human-corrected/re-investigated revisions cannot inherit approval; reviewer can compare versions.
- All privileged actions fail for unauthorized role and stale revision.
- Approved high-impact findings have mandatory rationale; bulk approvals do not bypass guardrails.
- Missing historical/financial/customer data is explicitly unknown or insufficient, never silently assumed routine.
- Every decision resolves to an identifiable reviewer, current revision and audit event.
- Code Review, independent QA and tests pass using deterministic data and mock AI calls.

**Post-release outcome metrics:** percentage of findings with resolvable evidence citations; time from generation to engineer validation and final Lead decision; frequency/reasons of return and permanent rejection; stale-action/permission incidents; percentage of decisions with complete auditable provenance. These are proposed metrics, not measured baselines or promises.

## 13. Delivery plan / proposed work breakdown

1. **Repository reconciliation:** inspect existing state, schemas, roles and UI; derive a feasible state-transition and permissions matrix.
2. **UX and API contract:** wireframes, action states, review version semantics, risk classification spec and endpoint contracts.
3. **Backend foundation:** revision history, decisions/audit, permissions, risk classification, transactional concurrency checks and tests.
4. **Frontend:** investigation findings list, evidence detail, Engineer actions, Lead queue/actions, version comparison and bulk approval.
5. **Integration QA:** synthetic scenarios, data-quality edge cases, negative tests, role matrix, performance/accessibility and independent review.
6. **PR/checkpoints:** small scoped features, independent Code Review + QA, guarded merge; no surprise files or unapproved provider calls.

**Recommended immediate next step:** Give Antigravity's Product/UX/System Design role this PRD and request a **repo-grounded gap analysis and a state/permission/API contract proposal**, not implementation. Verify the PR #14 merge result before beginning work on new branches.

---

**Change control:** Product decisions above are the MVP baseline. Any change to thresholds, role separation, audit invariants or remediation boundaries should be documented as an explicit PRD amendment with rationale and impact.
