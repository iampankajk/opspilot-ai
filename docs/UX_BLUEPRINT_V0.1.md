# OpsPilot AI — UX Blueprint v0.1

**Status:** Approved baseline, amended by owner-approved evidence-first redesign on 16 November 2026 (D-030–D-034).\
**Purpose:** Define the current investigation workbench, distinguish later product requirements, and provide bounded implementation/verification steps. The historical filename is retained to preserve existing links.

## 1. Scope and precedence

Implement the evidence-first redesign before Task 5B. The five approved wireframe views are session/incident entry, incident overview, selected-case evidence, expanded evidence record, and mobile navigation. Wireframes establish information architecture; final styling must be a polished professional operations dashboard.

The [Decision Log](DECISION_LOG.md) is the approval register. This amendment and the updated screen specifications govern the current redesign; [PRD v0.1](PRD_V0.1.md) remains the broader product baseline. Assistant conversation, findings, human review, numbered revisions/refresh/export, and annotations remain later requirements, not dependencies of this increment. The current instruction authorizes documentation only. Stop for review before application implementation; do not start Task 5B automatically.

No backend schema/API changes, new persistence contracts, dependencies, or operational actions are part of this redesign. Existing source records and evidence meanings are authoritative. Missing bank evidence, unverified provider completeness, and unresolved root cause remain intentional evidence limitations.

## 2. Workspace structure and visual direction

| Area | Current responsibility |
|---|---|
| Compact incident header | Incident identity/title, available severity/region/category, incident time/timezone, description when supplied, Synthetic Data indicator, and pinned dataset label |
| Persistent desktop navigation | Both investigation threads, configured-case counts, and cases within the active thread; selected thread and case remain distinguishable |
| Main workspace | Overview and Evidence; a visibly unavailable Findings destination with no findings API calls |
| Contextual disclosures | Case identifiers, readable record fields, provenance, relationships, technical payloads, request/workspace/session details |

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Incident identity · severity · region · incident time  Synthetic data│
│ Title / supplied description · pinned dataset          Session      │
├──────────────────┬──────────────────────────────────────────────────┤
│ THREADS          │ Active thread                                    │
│ Payment failures │ Overview | Evidence | Findings — unavailable      │
│ Possible         ├──────────────────────────────────────────────────┤
│ duplicates       │ Overview: compact case list                       │
│                  │ Evidence: compact selected-case context           │
│ CASES            │ Four source groups and scannable record rows      │
│ Active case      │ Readable details expand inline; no assistant panel│
└──────────────────┴──────────────────────────────────────────────────┘
```

Use the available desktop width, strong readable typography, a consistent spacing scale, subtle borders, and compact rows. Avoid a narrow centered document layout, a large introductory hero above the active investigation, excessive nested cards, and a separate scroll area for every source. Use one primary content scroll area. Keep compact incident and selected-case context visible on desktop; they may form one coordinated sticky region, rather than separate sticky toolbars for navigation, sources, notices, and records. Metadata must wrap and focused content must remain unobscured at zoom. Detailed panels scroll normally.

Connection diagnostics and technical IDs belong in labelled disclosures, with errors surfaced when action is needed. Session expiry and the inability to recover a lost/expired session must remain understandable. Do not introduce automatic session replacement.

## 3. Five views and navigation

### 3.1 Session / incident entry

1. Explicitly start or resume the anonymous demo session.
2. Enter a known incident reference and load its preview.
3. Explicitly create or resume the owned investigation.

Show incident identity, available scope metadata, and synthetic origin before entry. Keep credentials out of the UI. Session details and connection diagnostics expand on request. Existing investigation links may resume through the owned workspace GET with the current cookie; loading such a link does not bootstrap a replacement session or create an investigation automatically. No new incident catalog, saved-investigation list, or recovery feature is introduced.

### 3.2 Incident overview

On a fresh workspace view, select **Payment failures → Overview**, with **no active case**. A first visit to the other thread also has no automatically selected case. Show the active thread explanation, compact full case list, and configured-case count. A row includes the available case/customer references, reported concern and amount/currency, source-supported payment context, and investigation progress. Do not infer missing fields.

Search, filters, pagination, and virtualization are deferred for the current dataset. Do not substitute illustrative screen values or fixture prose for unsupported API metrics. Current workspace/case responses do not expose the planned aggregate metrics; show the supported configured-case count and omit aggregate cards. A case is not a complaint total, attempt count, customer count, or confirmed charge.

Keep reported order separate from candidate/related orders and preserve their basis references. Review progress remains **Not started** under the implemented contract; opening a case, retrieving evidence, or generating a future AI proposal is not human review. When human review is separately implemented, progress derives from claim decisions: none/no claims → Not started; some but not all → In progress; all linked claims reviewed → Reviewed. Reviewed does not mean resolved.

Selecting a case opens Evidence, sets that case active, and moves focus to its context. The row should support pointer activation across its useful area and a clearly named native keyboard action without duplicate nested interactions. Going to Evidence without an active case shows “Select a case” with a route to Overview; no silent selection or retrieval occurs.

### 3.3 Selected-case evidence

Show compact case identity, reported concern/amount, separate payment context and progress, and material evidence limitations. Additional identifiers and association bases expand on request. Keep all four source groups visible in stable order, including before retrieval:

1. Internal Payment Records — `internal_payments`.
2. Stripe / Payment Provider — `stripe`.
3. Logs & Traces — `loki`, `tempo`.
4. Support Tickets — `zendesk`, `support_lookup`.

Case selection, tab/thread navigation, source/record expansion, relationship links, and responsive layout changes send **no evidence POST**. The investigator explicitly chooses Inspect evidence; after success, Inspect again creates a new request. Retry is explicit and uses the existing retry-reference rules. Reinspection reads the pinned stored evidence; it is not full-dataset refresh or a new numbered revision. Retries operate on the existing whole case-evidence request, not an invented per-source API.

Before a first request show Not requested/count unknown, never zero. Loading preserves context. The current endpoint returns one terminal completed/partial response; no streamed per-source arrivals or background polling are promised. Render all returned source outcomes together and expose individual failures within partial results. A failed request must not become a no-match state.

### 3.4 Expanded record and related records

Each compact record row shows record type/ID, source identity, useful source-backed message/status, available timestamp/timezone/precision, and a short truthful “Why related” explanation. Source names may be inherited visually from the immediate group header but remain understandable to assistive technology.

Expand readable labelled fields inline without leaving Evidence. Multiple records may remain expanded; users can collapse any independently. Show key meaning before technical content. Preserve all original useful fields in readable details or the original-payload disclosure, including unfamiliar fields; formatting is not permission to infer typed payment analysis or rewrite source meaning.

Expose provenance, original timestamps and missing reasons, exact payload, matched fields, basis record, relationship attribution, and limitations through labelled disclosures. Preserve direct reference, documented lookup, field match, temporal context, and unverified association categories. No confidence percentages or inferred links. A supported cross-reference reveals its source group and target record, scrolls and focuses its summary, visibly identifies the target, and leaves other records expanded. Missing targets fail visibly without querying another scope or inventing evidence.

### 3.5 Mobile navigation

At narrow widths, replace the persistent desktop rail with a clearly labelled Threads & cases control and accessible drawer. Keep incident identity and Synthetic Data visible, with thread/case identity outside the drawer. The drawer lists both threads, active-thread cases, and selected states. Closing, Escape, or case selection returns focus predictably to the content or invoking control; modal focus stays inside the open drawer. Do not rely on hover.

Stack case fields and record details without dropping payment context, reported amount/currency, review progress, source grouping, or material limitations. Long identifiers and technical payloads remain readable/selectable. Collapse secondary metadata rather than the evidence-safety information. The assistant is absent on all sizes.

## 4. Provenance, coverage, and uncertainty

| Presentation level | Required information |
|---|---|
| Workspace | Synthetic Data indicator and pinned dataset label |
| Source header | Source identity, returned count when known, execution state, material availability/completeness limitation |
| Record row | Source-backed summary, available timestamp/precision, relationship basis |
| Expanded details | Full useful record content, related records, local limitations |
| Secondary disclosures | Exact payload, original timestamps/timezone/missing reasons, fixture origin/version/record ID, matched fields and technical metadata |

Keep execution separate from coverage: “Retrieval completed” never means “Complete evidence.” A successful Stripe read retains unverified completeness. Keep no matches (`0`) distinct from failed/interrupted/not evaluated (`null`, count unknown), not included, not constructed, and unavailable. Preserve the backend's availability, execution, match, and completeness dimensions even when concise labels are used. No positive outcome may be inferred from a source outcome alone.

Material limitations remain beside the affected source and record; they cannot be hidden only in general help. Consolidate repeated generic source descriptions, while keeping the possible-duplicate interpretation notice visible: multiple attempts do not establish multiple charges. Bank/settlement gaps are limitations, not fabricated zero-result sources or records. A customer report is evidence of what was reported. Attempts, requests, authorizations, captures, reversals/refunds, settlement, and bank posting remain distinct. No unsupported duplicate/nonduplicate or root-cause verdicts.

Preserve original event time, timezone, precision, ranges, and missing values. Convert to the incident timezone only when the source permits reliable conversion; never infer timezone from the device or manufacture seconds. Distinguish event, report creation, lookup, and retrieval times. In source groups, retain implemented oldest-to-newest ordering with unusable event times last. A provider extract can list several lifecycle references but is still one returned record; do not split it into invented records.

## 5. Session-local state and current API limits

Preserve selected view/case, valid locally returned evidence, source/record/disclosure expansions, and scroll position across Overview/Evidence and thread switches in the current loaded page. Scope state by investigation/state/thread/case and keep returned evidence associated with its exact evidence-request ID. Never display another scope's result during a switch or after a late response. Replacing evidence for a new explicit request must not merge it with a previous request or silently discard its limitations. Draft-version increments are concurrency metadata, not numbered revisions.

This is client memory, not new durable browser storage or backend persistence. A full page reload may reopen the investigation through the existing URL/GET, then defaults to Payment failures → Overview with no case selected; it does not promise restoration of earlier evidence responses, request lists, or expansion state. A same-scope workspace GET is not evidence reinspection. Clear incompatible local context on investigation/state changes or confirmed invalid/expired authorization. Follow existing stale-state/version recovery and current-version reconciliation before an explicit retry; UI cancellation does not imply that server execution was cancelled. No automatic POST retry, source refresh, or durable resumption.

| Existing operation | Redesign use / boundary |
|---|---|
| Visitor-session POST | Explicit start/resume; no credential display or automatic replacement |
| Incident GET; investigation POST; workspace GET | Existing entry/create/resume/reload flow; preserve ownership and error handling |
| Thread cases GET | Scoped case list; retain response validation |
| Case evidence-requests POST | Explicit bounded case inspection/reinspection/retry, current version and retry reference |
| Locally returned evidence | Inline expansion and relationship navigation; no additional record-detail calls |
| Durable evidence history | Preserve existing current-view request list; no full-history browsing/readback endpoint exists |
| Task 5A findings GET/POST | Existing backend/mock capability, deliberately unused by this redesign |

Keep same-origin cookie handling, no-store behavior, safe errors, scope validation, and authorization unchanged. Render source text as data, never executable HTML or instructions. Do not introduce arbitrary SQL, filters, URLs, fixture paths, or evidence-selection overrides.

## 6. Responsive and accessibility verification targets

Validate desktop layouts at **1440×900** and **1280×800**, a compact layout at **1024×768**, and mobile widths **390px** and **320px**. These are acceptance viewports, not mandatory CSS breakpoint values. Choose breakpoints from content fit. Target WCAG 2.2 AA; do not claim conformance from design review or an automated scan alone.

Require keyboard access, visible unobscured focus, semantic headings/landmarks, named navigation/actions, text with status colors, announced disclosure state, appropriately associated errors, and restrained loading/status announcements. Check normal-text contrast at least 4.5:1, large text and essential UI indicators at least 3:1, and applicable WCAG 2.2 target-size requirements; aim for 44px touch targets. Respect reduced motion. Verify 200% text zoom and reflow equivalent to 320 CSS pixels/400% zoom, preserving all core actions and fields. Avoid whole-page horizontal scrolling; any necessary technical-content scrolling must be local and keyboard accessible.

## 7. Bounded implementation increments

These are planned increments, not completed implementation or permission to begin. Owner-led implementation stays small and reviewable; no library choice or installation is implied.

| Increment | Included work | Exit evidence |
|---|---|---|
| UX-1 — Entry and shell | Explicit session/incident flow, compact header, desktop rail, Overview/Evidence navigation, unavailable Findings, disclosures and professional visual primitives | UX-R01–R04 and R17; entry/resume screenshots and network trace |
| UX-2 — Case selection and local context | Compact Overview, explicit selection/no-selection state, per-thread/case local state, scoped late-response handling | UX-R05–R08 and R15; both-thread keyboard/navigation walkthrough and meaningful interaction checks |
| UX-3 — Evidence inspection | Explicit retrieval/retry, four groups/six outcomes, readable records, progressive disclosure, contextual links, original payload/provenance fidelity | UX-R09–R14 and R16; both seeded cases plus controlled exceptional-state evidence |
| UX-4 — Responsive, accessibility, and regression acceptance | Mobile drawer/reflow, focus/zoom/contrast checks, final density refinement, existing contract and Task 4B regression checks | UX-R18–R21 and all earlier criteria; recorded browser/check results with remaining issues |

## 8. Measurable acceptance criteria

All criteria below are **pending implementation/verification**. They operationalize the approved direction, not a claim of new user research, measured productivity, or current conformance.

| ID | Required observation |
|---|---|
| UX-R01 | On a fresh open, Payment failures and Overview are selected; no case is active. Direct Evidence entry without selection offers a case-selection path and sends zero evidence POSTs. |
| UX-R02 | Explicit session → incident preview → create/resume completes using existing operations. Existing investigation URL resumes by owned GET; expired/invalid sessions show a recovery explanation without silent replacement or leaked credentials. |
| UX-R03 | At 1440×900 and 1280×800, incident identity, active thread, Overview/Evidence navigation, and configured-case count are visible without scrolling through setup/diagnostic panels. |
| UX-R04 | Both threads remain available on desktop. Findings visibly says unavailable, cannot activate generation/review, and sends zero findings calls. No assistant/chat, search/filter, revision, refresh, or export controls appear. |
| UX-R05 | Each seeded case is selectable by pointer and keyboard and opens Evidence with the correct case identity. Reported and candidate orders remain separate; money retains exact amount text and currency. |
| UX-R06 | Returning to Overview restores position. Switching threads and back restores that thread's view/case and, after an explicit retrieval, its local result and expansion/scroll state with zero new evidence POSTs. |
| UX-R07 | Full reload restores the owned investigation/state through the existing contract, defaults to Payment failures → Overview/no case, and sends zero evidence POSTs. No previous evidence response/history restoration is advertised. |
| UX-R08 | Switching case/thread/state during an in-flight operation never displays the late response in another scope. Invalid/expired authorization clears protected local context. Stale-state/version recovery preserves explicit retry and does not silently select a replacement case. |
| UX-R09 | Case/tab/thread/record/source/relationship navigation and layout changes send zero evidence POSTs. Each explicit Inspect/Inspect again or eligible Retry issues at most one evidence POST, preserves request identity/version rules, and never claims dataset refresh. |
| UX-R10 | All four groups and all six source outcomes remain identifiable before/during/after retrieval and in errors. Before retrieval counts are unknown. Terminal responses render without claiming streamed source completion. |
| UX-R11 | Baseline returned group record counts are failure **1/1/2/1** and possible duplicate **2/1/0/3**. Loki and Tempo zero matches remain separate outcomes; the provider extract stays one record regardless of lifecycle references inside it. |
| UX-R12 | Controlled presentation cases distinguish not requested, loading, zero matches, not included, not constructed, unavailable, failed, interrupted, partial result, and stale/session errors. Failed/not-evaluated counts never appear as zero; completed retrieval never upgrades coverage. Use isolated test responses, not edits to the frozen fixture or API. |
| UX-R13 | Every returned record has readable identity/source, useful source-backed summary, timestamp or missing-state label, and association explanation. Complete original payload and provenance remain inspectable; unknown fields are retained. Raw JSON is closed by default. |
| UX-R14 | Multiple records can stay expanded and collapse independently. Each supported related-record link reveals its group/record, moves focus to the summary, and leaves the originating record open without a network request. Matched fields, category, basis, attribution, and limitations match returned data. |
| UX-R15 | Opening/retrieving records never changes Not started to In progress/Reviewed. No case-level payment outcome is inferred from internal attempt or provider events, and no unsupported metric is displayed. |
| UX-R16 | Both baseline cases retain source timestamps/timezones/precision, missing times, and implemented source chronology. The Zendesk duplicate report precedes its 10:40 SGT escalation. Provider completeness/bank gaps remain visible with provider evidence; no duplicate/nonduplicate or root-cause verdict is added. |
| UX-R17 | Setup and diagnostic prose no longer precede an active workspace. Case lists use compact rows; evidence rows do not repeat full source descriptions. At desktop target heights, the case identity, retrieval action, and at least the first source heading are visible on Evidence entry. At most one coordinated incident/case sticky region is used; source headings/toolbars/records do not each stick. |
| UX-R18 | At 1024px and mobile target widths, navigation adapts without dropping incident/case identity, source headings, amount/currency, payment context, progress, limitations, or actions. No whole-page horizontal overflow. Mobile drawer closes with Escape/Close, contains modal focus, and returns focus predictably without losing context. |
| UX-R19 | Complete both seeded journeys with keyboard alone: entry/resume, thread/case selection, inspection, expansion, relationship traversal and return. A screen-reader walkthrough confirms names, selected/disclosure states, errors, and restrained loading announcements. Focus is never hidden behind sticky content. |
| UX-R20 | Record contrast, target-size, reduced-motion, 200% text-zoom and 320-CSS-pixel/400%-zoom reflow checks. All required content/actions stay available. Record any WCAG failures; do not label the result AA-conformant while unresolved failures remain. |
| UX-R21 | Run the repository's frontend tests, TypeScript check, and production build; verify changed interaction behavior meaningfully and retain existing scope/parser tests. Repeat both Task 4B focused browser regressions (relationship target expansion and chronology) plus broader entry/reload/error/responsive smoke checks. Report actual commands/results; existing backend verification is historical, not rerun by documentation. |

## 9. Future product requirements retained

The original broader workspace journey continues from evidence to AI-proposed findings, individual human acceptance/correction, and eventually saved revisions and reviewed export. These features are deliberately absent from current redesign acceptance. The two Findings specifications remain future design references; Task 5B must separately reconcile its narrower case/thread/state/request-bound unreviewed proposals with those full-product screens.

Preserve AI proposal versus human decision, Confirmed/Not confirmed/Inconclusive meanings, no bulk acceptance, and a mandatory nonblank correction rationale in both threads (D-010). Later progress derives from recorded claim decisions, not opening evidence. Future assistant conversations must preserve thread/case context, cite evidence, and avoid silent cross-thread mixing; no conversation UI is implemented here. Numbered save/whole-dataset refresh/read-only history/export retain D-009–D-013 and PRD rules; draft-version counters and evidence reinspection do not implement them.

## 10. Explicit reconciliation with earlier specifications

| Earlier clause / document | Current resolution |
|---|---|
| Blueprint and all six screens: persistent three-column layout/assistant | Superseded for this increment by header + rail + main content. Assistant requirements are future only; no empty right column is reserved. |
| Overview/Evidence search and filter controls, filter-empty states | Deferred for this dataset. Show the full list and source groups; no search/filter acceptance is required now. |
| Overview aggregate example metrics and larger illustrative case lists | Future source-backed design only. Current APIs support configured-case counts; illustrative figures and extra cases must not be hardcoded. |
| Findings navigation, claim review and assistant journey in current screens | Findings is unavailable; no findings integration/review in this redesign. Full-product findings/revision/export requirements remain future. |
| Duplicate Overview: progress based on inspecting evidence | Replaced with recorded claim-review derivation, matching Payment Failures and D-010/Task 5 scope. Current progress remains Not started. |
| Payment Failures Findings: optional correction note | Superseded by D-010: correction rationale is mandatory in both threads when review is later implemented. |
| Evidence selection wording that could imply retrieval on entry | Selecting a case navigates only. Inspect evidence, Inspect again, and Retry are explicit bounded operations. |
| Payment Failures Evidence: independently arriving source results | Future possibility only; current endpoint returns one terminal response. Display individual returned outcomes, not invented streaming/per-source retry. |
| Revision-scoped preservation/reopening language in active Evidence views | Current UI state is local to the loaded page. Existing durable workspace/history remains; no prior response readback, numbered revision or new history endpoint is implied. |
| Duplicate Overview's saved-investigation Home ordering reference | Not part of this increment; no saved-investigation Home API/UI is introduced. Preserve existing returned case order without new sorting controls. |
| Earlier responsive/sticky choices listed as open | Direction resolved by D-030/D-033; exact tokens and content-driven breakpoints are implementation detail, checked against §6/§8. |
| Earlier first-pass completion checklists | Historical design completion, not evidence of implementation, browser verification, accessibility conformance, or current-increment feature availability. |

## 11. Review state and remaining dependencies

Owner approved the five-view information architecture and visual refinement on 16 November 2026. This document records that approval; updated documentation still stops for owner review. No unresolved product choice blocks the bounded redesign. Exact typography, spacing tokens, colors, and breakpoint values remain routine visual refinement within the approved direction; introduce no major dependency without a separate need/approval discussion.

Implementation, browser verification, and accessibility acceptance remain pending. Earlier wireframe structure/script checks did not establish visual correctness; browser preview was blocked by a local-file URL policy. Task 4B's broader visual follow-up remains part of UX-4, distinct from its two previously passed focused fixes. Task 5A's owner-reported merge does not supply frontend findings or live-model verification. Separate credential-rotation/hosting/provider follow-ups in Project Status remain outside this documentation task.
