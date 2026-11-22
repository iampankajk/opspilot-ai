# UX Increment 3 — Evidence Readability

Implementation and verification record for 20 November 2026. Review baseline: D-030–D-034, UX Blueprint UX-R09–R14/R16, and both approved Evidence screen specifications. This increment does not authorize UX-4 or Task 5B.

## Starting checkpoint and scope

Verified before editing:

- Branch: `codex/task-5ux-workspace-redesign`.
- HEAD: `e89286056cffba63e25b86bc0ca309551ca954c7` (approved Increment 2 checkpoint).
- Working tree: clean.

Only frontend presentation, the existing relationship-reveal behavior needed by collapsible record lists, tests and progress documentation change. No backend, authorization, schema, API, fixture, package/lockfile or dependency changes. No commit, push, merge or PR.

## Changed files and design

| File | Responsibility |
|---|---|
| `frontend/app/evidence-view.tsx` | Compact groups, six explicit source states, readable records, contextual relationships and technical disclosures |
| `frontend/lib/evidence-presentation.ts` | Source labels, exact source-backed summary selection, timestamp selection, known/unknown counts and field presentation |
| `frontend/app/globals.css` | Compact source boundaries, flat record rows, labelled fields and focus/target styling |
| `frontend/app/evidence-panel.tsx` | Pass the existing active thread to presentation so the duplicate notice is present before retrieval |
| `frontend/lib/evidence.ts` | Correct not-evaluated outcome copy; reveal enclosing disclosures before target expansion |
| `frontend/app/case-workspace.tsx` | Use the same reveal helper during fragment-history restoration; remove the redundant duplicate interpretation notice |
| `frontend/tests/evidence.test.mjs` | Presentation fidelity, exceptional-source states, contextual links and disclosure regressions |
| `frontend/tests/case-navigation.test.mjs` | Preserve the multi-case retention assertion using the Evidence panel rather than its former positional child index |
| `frontend/tests/evidence-readability.browser.mjs` | Mounted seeded-case presentation, payload, limitation and chronology checks |
| `frontend/tests/workspace-regressions.browser.mjs` | Adapt existing relationship/history checks to contextual links; verify collapsed source-list revealing |
| `docs/PROJECT_STATUS.md`, this file | Current implementation, verification and remaining limits |

The presentation layer selects existing source wording. It does not analyze payments. Every field remains in readable details or technical disclosures and in the original JSON payload. Unknown/nested fields render as plain React text and labelled values; strings, exact money text, missing values and all payload keys remain intact. No markdown/HTML from sources is executed.

Collapsed rows show record identity/type, source-backed status/message, a supplied timestamp with role/timezone/precision or missing-state label, and the returned case-association explanation. The source is available through the immediate group/outcome and an explicit accessible record label. Expanded records show readable labelled fields first. Secondary disclosures expose identifiers/source fields, association/matched fields, original timestamps/UTC bounds/missing reasons/provenance, and original JSON. JSON is closed by default.

Each related-record link belongs to an expanded originating record. Its accessible description points to the returned relationship category and explanation; exact attribution, matched fields, basis record, relationship ID/direction and limitations remain inspectable. Links reveal collapsed enclosing lists and their target, preserve other expanded records, use existing scoped fragments, and focus the target summary. Missing returned targets have a visible unavailable message; the unchanged parser rejects dangling response references.

All four source headings and all six outcomes appear even before retrieval and after request errors. Source execution, availability, match status and evidence completeness stay separate. Unknown counts never become zero. Source states and material limitations remain visible even when record lists are collapsed. The repeated generic synthetic notice is consolidated above the groups; exact source limitations remain available in each source's metadata disclosure. Provider completeness and missing bank/settlement evidence remain beside provider evidence. Multiple attempts remain distinct, and the provider extract remains one returned record.

The existing explicit inspection/reinspection/retry and request-version/scope logic is retained. Local state remains scoped page memory. Opening records, following relationships or navigating does not implement human review, numbered revisions or dataset refresh. The duplicate interpretation notice is visible before/during/after requests.

## Acceptance evidence

| Criteria | Evidence |
|---|---|
| UX-R09 | Existing request/scope/rapid-activation/explicit-retry tests pass. Browser/access-log accounting: five explicit evidence POSTs, zero extra navigation POSTs and zero findings calls. Explicit reinspection adds one distinct request ID. |
| UX-R10, UX-R12 | Actual presentation tests cover idle/loading/request failure, six identities, separate zero/not-evaluated/not-included/not-constructed/unavailable/failed/interrupted outcomes and partial responses. Existing stale/version/session tests remain. No frozen fixture or API mutation. |
| UX-R11 | Frozen seeded payload render tests retain failure 1/1/2/1 and duplicate 2/1/0/3; one provider extract. Mounted checks pass for both cases at both desktop sizes. |
| UX-R13 | Exact-payload comparisons, unknown/nested fields, source-safe text, readable fields, source-backed summaries, timestamp roles/ranges/missing states and closed JSON disclosures verified in tests. |
| UX-R14 | Contextual links have associated explanations and exact relationship data. Handler tests verify reveal/focus/modifier clicks/independent expansion. Enclosing-list reveal, pointer/Enter targets, native Tab/Shift+Tab and mounted fragment/history checks pass at both desktop sizes. |
| UX-R16 | Original timestamp text/timezone/precision/UTC bounds/missing reasons are retained; source ordering is untouched. Provider/bank limitations remain visible and tested. Mounted Zendesk chronology passes: ticket 10:33 SGT precedes escalation 10:40 SGT; lookup remains in its original source. |
| Preserved UX-R06–R08, R15 | Mounted view/thread/record/disclosure retention, browser Back/Forward, scroll/focus repair and Not started behavior pass. Existing authorization/stale-response component tests pass; live expiry/stale responses were not forced. |

## Executed checks

From `frontend/`, using Node **22.21.1** with its bin directory first in PATH:

```sh
npm test
npm run typecheck
npm run build
```

- Frontend tests: **57 passed, 0 failed/skipped** (48 retained tests plus nine new presentation/reveal tests).
- TypeScript: passed (`next typegen && tsc --noEmit`).
- Production build: passed after final presentation refinements, including TypeScript/static generation.
- `git diff --check`: passed. The generated `next-env.d.ts` change was restored to the approved checkpoint; direct `tsc --noEmit` also passed after restoration.

The Node tests use actual React rendering and actual event handlers with the repository's existing deterministic component harness. They do not replace mounted browser focus, scroll, history or accessibility verification. No backend tests or frontend lint pass is claimed; no frontend linter/script exists.

## Executed browser verification — 20 November 2026

The owner handled the local certificate warning. Connected Chrome used the real local HTTPS application and existing backend APIs. Explicit session resume, incident preview and owned investigation entry succeeded. Both seeded cases were explicitly inspected. A development hot update after the notice fix reset local Evidence component responses; two further explicit setup inspections established the final unchanged-code test session. This development reload is not a promise of durable response restoration.

Executed browser modules through the connected browser's documented APIs:

```js
await checkEvidenceReadability(tab, expectedCounts, expectedPayloads);
await checkTechnicalDisclosures(tab);
await checkNativeEvidenceKeyboardJourney(tab);
await checkWorkspaceRegressions(tab, viewport);
await checkThreadContext(tab);
await checkReviewHistoryRegressions(tab, viewport);
await checkRetainedEvidenceKeyboardFocus(tab, viewport);
```

`expectedPayloads` came from the unchanged repository fixture. Page evaluation inspected rendered DOM only, not framework internals or application state. Selector waits were used for terminal responses and workspace reloads; an initial immediate request-history read occurred before reinspection completed and was corrected by waiting for the terminal Inspect again control. No second activation or automatic retry resulted.

| Check | 1440×900 | 1280×800 |
|---|---|---|
| Failure case readability/payloads | Pass: 1/1/2/1; all five exact payloads | Pass: same |
| Duplicate case readability/payloads | Pass: 2/1/0/3; all six exact payloads | Pass: same |
| Source semantics | Four groups/six outcomes; Loki and Tempo separately show zero matches for duplicate; provider extract remains one record | Pass: same |
| Technical disclosures | Native keyboard opening/collapse of identifiers, case association/matched fields, timestamps/provenance, relationship attribution/basis and source scope/match details | Pass: same |
| Original payload | Closed by default; opens and collapses by keyboard; values/keys match frozen source payloads | Pass: same |
| Coverage/interpretation | Provider completeness and bank gap remain local; exact expanded record limitations remain readable; duplicate notice appears once | Pass: same |
| Native keyboard journey, both cases | Tab from Inspect again → source list; Enter collapse; Tab skips hidden records; Shift+Tab/reopen; Tab → record → contextual link; Enter reveals/focuses target and preserves origin; target collapses independently | Pass: same |
| Pointer and Enter failure-provider link | Target top/bottom **163.09/275.59px**, below header **146px**; target/origin expanded | **162.06/274.56px**, below header **144.97px** |
| Relationship history into a collapsed list | Back restores case/view/fragment and reveals/focuses target; target top **162.09px**, header **146px** | Target top **161.06px**, header **144.97px** |
| Direct duplicate Evidence Back/Forward | **3604 → 3604px**, two cycles; exact responses and both Zendesk expansions retained | **1925.5 → 1925.5px**, two cycles; same retention |
| Retained Evidence keyboard return | **2125.5 → 2125.5px**; visible focus inside Evidence on source-details summary, **338.40–374.40px**; native Tab/Shift+Tab and pointer behavior pass | **1925.5 → 1925.5px**; focus **265.37–301.37px**; same checks pass |
| Full reload/no-selection boundary | Owned GET resumes Payment failures → Overview/no case, no prior Evidence panels; Evidence offers Select a case/Go to Overview | Pass: same |

Thread switches retain exact local request histories and disclosure states. Returned record summary identities, source-backed status/messages, association explanations, original timestamp text/timezone/precision and source chronology were checked. The duplicate Zendesk ticket at 10:33 SGT precedes its 10:40 SGT escalation. Internal attempts, provider requests, authorization/capture and missing bank posting remain distinct. Review remains Not started. No whole-page horizontal overflow was observed at either requested desktop size. Chrome's captured error log was empty at the end of verification.

### Defect found and fixed

The duplicate interpretation warning initially appeared twice: the retained workspace notice and the new Evidence notice. Removed only the redundant workspace paragraph. The Evidence notice remains visible before/during/after requests; provider completeness/bank gaps remain local to provider evidence. The final browser DOM contains one interpretation notice. An existing component test used the former child's numeric position; its assertion now locates the Evidence panel by component identity while continuing to prove independent same-thread case retention. No navigation/request behavior changed for this fix.

One initial browser-script invocation assumed Evidence responses survived the development hot update; it was restarted after explicit setup inspections. Another invocation expected an Overview row when thread memory correctly restored Evidence; it was corrected to use the actual retained view. These were test-driver precondition issues, not additional application defects. No unresolved defect was observed in the requested desktop checks.

### Request accounting and artifacts

The temporary backend access log contains exactly **five evidence POSTs**: initial inspection of both cases, explicit setup inspection of both cases after the development update, and one explicit failure-case reinspection. The final navigation/relationship/disclosure/history windows contain **zero unintended evidence POSTs**. **Zero findings calls** were recorded. Reinspection retained the old local request ID and added one new distinct ID; response replacement reset record disclosures rather than merging the previous response. Full reload sent no evidence POST.

Artifacts outside Git:

- `/private/tmp/opspilot-ux3-access.log` — methods/paths/statuses only, no credentials/headers/bodies.
- `/private/tmp/opspilot-ux3-duplicate-1440.jpg` — compact case, retrieval action and readable attempt rows.
- `/private/tmp/opspilot-ux3-failure-relationship-1280.jpg` — focused provider target, readable fields, local limitations and closed technical disclosures.
- `/private/tmp/opspilot-ux3-tests-final.log` — final frontend suite.

Viewport override reset. Only temporary local frontend/backend verification processes are stopped; no unrelated server is stopped. The claimed user tab remains on the default Overview.

## Final status and limitations

Increment 3 implementation and requested desktop browser verification are complete, with **57/57 frontend tests**, TypeScript, production build, restored-declaration TypeScript and diff checks passing after the notice fix. Work remains uncommitted for owner review; this is not an independent Code Review/QA approval.

Comprehensive responsive/mobile-drawer, screen-reader, contrast, target-size and zoom acceptance belongs to UX-4 and remains unverified. No WCAG conformance or other-browser result is claimed. Controlled exceptional outcomes and authorization/stale-response races are isolated presentation/component tests, not forced live source failures or session expiry. Page reload intentionally does not restore earlier evidence responses. Backend tests were not rerun for this frontend-only work. Findings, human review, assistant, exports and live model calls remain outside this increment.

Recommended next step: owner review of the uncommitted Increment 3 diff and acceptance evidence. Stop; do not begin UX-4, commit, push, merge or create a PR.


## Independent review P3 follow-up — 20 November 2026

The owner reports Increment 3 passed independent Code Review and QA with one non-blocking P3 readability observation. The earlier notice fix removed the duplicate selected-case paragraph but missed semantically overlapping wording in the shared thread description. Its browser assertion inspected only the selected-case parent and matched only “Multiple payment attempts”; it could not detect the shorter thread-level “Multiple attempts” caution. This follow-up addresses only that observation.

### Bounded changes

| File | P3-only change |
|---|---|
| `frontend/app/workspace-shell.tsx` | Neutral Possible duplicates thread description; no repeated interpretation caution |
| `frontend/app/evidence-view.tsx` | One persistent case/evidence caution explicitly retains the multiple-attempts distinction and the possibility of missing independent financial/bank/settlement evidence |
| `frontend/tests/evidence-readability.browser.mjs` | Count both wording variants across the entire rendered workspace using `workspace.innerText`; hidden views/disclosures are excluded. Focused calls also require the Evidence notice to be inside the viewport below the incident header |
| `frontend/tests/workspace-shell.test.mjs` | Assert the neutral description in Overview and Evidence |
| `frontend/tests/evidence.test.mjs` | Verify both parts of the caution in idle, loading, failure and completed-result presentation |
| `docs/PROJECT_STATUS.md`, this report | Record the owner-reported review result and bounded fix/verification |

The consolidated notice reads: “Multiple payment attempts do not establish multiple customer charges. Independent financial evidence, including bank/settlement records, may still be missing.” It stays in the selected-case Evidence context before and after retrieval. Provider-specific limitations remain next to provider evidence. No request, navigation, evidence value, backend contract, dependency or other feature changes.

### Executed verification

Node **22.21.1**, from `frontend/`:

```sh
npm test
npm run typecheck
npm run build
```

- **58 tests passed, zero failed/skipped**.
- TypeScript and production build passed.
- Generated `next-env.d.ts` restored to the checkpoint; direct `tsc --noEmit` passed afterward.
- Browser-module syntax and `git diff --check` passed.

Connected Chrome against the real HTTPS app, using the seeded possible-duplicate case and one explicit inspection:

```js
await checkDuplicateCaution(tab, true);
```

| Viewport | Before retrieval | After retrieval |
|---|---|---|
| 1440×900 | Exactly one caution across the complete visible workspace; both warning parts present; visible below header | Same: pass |
| 1280×800 | Exactly one caution across the complete visible workspace; both warning parts present; visible below header | Same: pass |

The browser check includes the thread description, not only selected-case content. The temporary access log contains exactly one evidence POST, corresponding to the explicit inspection, and zero findings calls. Viewport overrides reset; verification tab closed; only this follow-up's frontend/backend processes stopped.

Artifacts outside Git: `/private/tmp/opspilot-ux3-p3-caution-1280.jpg`, `/private/tmp/opspilot-ux3-p3-caution-1440.jpg`, `/private/tmp/opspilot-ux3-p3-tests.log`, `/private/tmp/opspilot-ux3-p3-access.log` (methods/paths/statuses only).

No unresolved issue was observed in this focused check. This is not a new full independent QA pass: broader Increment 3 browser evidence remains recorded above, while full mobile/accessibility, screen-reader, contrast and zoom acceptance stays deferred to UX-4. Backend tests were not rerun for this wording-only fix. No commit, push, merge, PR, or Increment 4. Stop for owner review of this bounded follow-up.


## Final acceptance and checkpoint authorization — 22 November 2026

The owner reports that Increment 3 passed independent Code Review and final QA, including verification of the resolved P3 duplicate-caution observation. The subsequent instruction authorizes creating and pushing the accepted checkpoint only after branch, parent, full tracked/untracked inventory, content/sensitive-data and staged-diff verification.

Verified branch: `codex/task-5ux-workspace-redesign`. Verified local HEAD and existing remote feature-branch tip before checkpoint creation: `e89286056cffba63e25b86bc0ca309551ca954c7` (approved Increment 2 parent). The reviewed checkpoint scope is exactly **14 files**: two documentation files, five application components/styles, two evidence libraries and five frontend/browser test files listed in this report, including the P3 additions. The application components/styles are `case-workspace.tsx`, `evidence-panel.tsx`, `evidence-view.tsx`, `workspace-shell.tsx` and `globals.css` (five files); the five test files are `case-navigation.test.mjs`, `evidence.test.mjs`, `workspace-shell.test.mjs`, `evidence-readability.browser.mjs` and `workspace-regressions.browser.mjs`. Thus the exact grouping is **two documents, five components/styles, two libraries and five test files**.

Application and test contents remain the QA-approved implementation. Checkpoint preparation updates only this report and Project Status to record final acceptance and publication authorization. Credentials, generated artifacts, local configuration, screenshots/logs, backend/contracts/dependencies and unrelated files are excluded. Earlier test/browser results and limitations remain recorded above; this Git checkpoint task does not rerun or broaden application verification.

Authorized commit message: `feat(ux): improve evidence readability and contextual inspection`. Stage only the reviewed files, inspect the staged diff and run `git diff --cached --check` before committing. Push only to the existing remote feature branch. Stop afterward: no PR, merge, branch deletion, application code change or Increment 4.
