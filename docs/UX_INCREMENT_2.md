# Task 5-UX — Increment 2: Case Navigation

Implemented on 16–19 November 2026, including the three code-review fixes and subsequent independent-QA focus fix. The owner reports final Code Review and independent QA passed and authorizes the verified Increment 2 Git checkpoint. Earlier implementation/fix handoff records below are historical. This record covers UX-2 only under the approved UX Blueprint and D-030–D-034; UX-3, UX-4 and Task 5B remain deferred.

## Starting point

Before editing, verified:

- Branch: `codex/task-5ux-workspace-redesign`.
- HEAD: `df038a827aaf54a80448789fb8bb30df65946788` (approved UX-1 checkpoint).
- Working tree: clean.

On resuming on 18 November, branch/HEAD still matched and the working tree contained the uncommitted UX-2 work, including a generated Next.js type-reference change subsequently restored to its checkpoint content.

## Result and design

Overview now shows compact case rows with one full-row native button per case. It preserves returned order, exact reported amount/currency text, concern/customer references, reported order separately from related/candidate orders and their basis, available payment context/limitations, and Not started review progress. The only incident/thread count is the existing configured-case count. Missing fields are explicit; no attempt counts, payment verdicts, incident metrics, or review progress are inferred.

The rail lists cases for the active thread and distinguishes selected-thread and selected-case states. Selecting a row or rail case opens Evidence and focuses that case's context. Direct Evidence navigation without selection offers a path to Overview. Selection and navigation do not call the evidence endpoint; Inspect evidence remains explicit.

`CaseWorkspace` owns page-local view/case navigation and case lists. Visited case panels remain mounted but hidden outside their active thread/case/view, retaining their own response, exact request history/retry reference, native disclosures, and expansions. Scroll positions are recorded separately for each thread's Overview and each case's Evidence. The small approved dataset permits this simple retention strategy; larger datasets would need another design.

The parent keys this local context by investigation, state, dataset identity, and fixture digest. Draft-version changes alone do not discard valid evidence. Confirmed stale-state or authorization/ownership failures unmount protected context; stale-state recovery requires an explicit workspace reload. Client requests abort on teardown and ignore late results. UI abort does not cancel or roll back server work. Evidence preflight checks the current scope/version before POST, and stale-version recovery does not retry automatically.

Record fragments include thread/case identity so retained panels cannot share DOM IDs or relationship targets. A new explicit evidence request replaces its predecessor rather than merging results; source/relationship disclosures reset for that new response. Record presentation otherwise retains the existing Task 4B UI, payloads, provenance, chronology, relationships, and limitations. Readable record redesign remains UX-3.

Local navigation uses browser history while preserving relationship fragment URLs. History entries have a page-specific scope token, so old entries cannot resurrect discarded context after reload/invalidation. Full reload resumes the owned investigation through the existing URL/GET, then starts at Payment failures → Overview/no case. No browser storage or new persistence/history API is added.

## Changed files

| File | Purpose |
|---|---|
| `frontend/app/case-workspace.tsx` | Scoped page-memory coordinator, per-thread/case navigation, mounted retention, scroll/focus/history handling, case loading |
| `frontend/lib/workspace-navigation.ts` | Scope identity, invalidation rules, validated local-history locations and scroll keys |
| `frontend/app/case-list.tsx` | Compact Overview rows and selected-case context/reference disclosure |
| `frontend/app/workspace-shell.tsx` | Active-thread case-navigation slot and retained selected-case Evidence content |
| `frontend/app/investigation-panel.tsx` | Scope-keyed workspace mount, invalidation/recovery boundary, monotonic version display |
| `frontend/app/evidence-panel.tsx` | Scope-aware preflight/recovery, protected-context invalidation, panel-specific fragment prefix |
| `frontend/app/evidence-view.tsx` | Scoped record/link IDs and request-bound disclosure reset; existing record presentation retained |
| `frontend/app/globals.css` | Compact case/navigation/context layout and focused-context clearance |
| `frontend/tests/case-navigation.test.mjs` | Scope, navigation, multiple-case retention, delayed/unmounted operations, retry and invalidation regressions |
| `frontend/tests/evidence.test.mjs` | Record/link fragment isolation regression |
| `frontend/tests/workspace-regressions.browser.mjs` | Updated selected-case journey; relationship, keyboard, thread retention, scroll and Back/Forward checks |
| `docs/PROJECT_STATUS.md` | Current milestone and verification boundaries |
| `docs/UX_INCREMENT_2.md` | This implementation/acceptance record |

No backend, API, migration, fixture, dependency, lockfile, or approved specification changes.

## Acceptance evidence

| Criterion | Evidence and boundary |
|---|---|
| UX-R05: explicit pointer/keyboard selection; accurate case context | Native full-row/rail buttons; Chrome keyboard failure-case selection and pointer duplicate-case selection open the correct Evidence context. Failure-case rail keyboard selection also passes. Focus clears the sticky incident header. SGD 48.00/SGD 120.00 stay exact; duplicate reported order remains missing while candidate SYN-ORD-002 retains SYN-ZD-HANDOFF-001 as basis. Render tests protect the same contract. |
| UX-R06: per-thread view/case/result/expansion/scroll retention | Component-handler tests cover first entry/no selection, independent thread locations and multiple cases within one thread. Chrome checks preserve both cases' exact request identities/disclosures across thread switches and Overview/Evidence; native-pointer return restores scroll exactly. Back restores the duplicate thread at 2496.5 CSS px; Forward restores Payment failures. Same-scope workspace GET retains the local responses/history. |
| UX-R07: full-reload defaults | Chrome full reload resumes the workspace at Payment failures → Overview, with zero active cases and zero retained Evidence panels. Traversing an old history entry afterward does not restore discarded case context. |
| UX-R08: scope changes, late work, authorization and explicit recovery | Controlled component/effect tests cover delayed originating-case responses, unmounted response rejection, changed-state preflight with zero evidence POSTs, expired authorization, parent removal of protected context, no late-version resurrection, mismatched-state retry-reference rejection, and unrelated-incident 404 preservation versus owned-workspace 404 invalidation. Existing parser tests reject investigation/state/thread/case mismatches. Stale-version recovery reconciles workspace metadata and leaves retry explicit. These exceptional states were not forced against the live database/browser session. |
| UX-R15: inspection is not review; no invented payment outcomes/metrics | Render/parser tests and both Chrome journeys retain Not started. Overview displays source-supported payment context and configured-case counts only. No human-review/findings controls or calls were added. |
| Supporting UX-R01/R17 | No-case Evidence path and keyboard return-to-Overview focus pass. At 1280×800, selected-case focus is visible and the explicit retrieval action/first source heading are visible on entry (bottoms 485.20/545.70 CSS px). |
| Existing Task 4B regressions | At 1440×900 and 1280×800, pointer/Enter relationships open/focus the target below the header, keep the origin open, retain native fragments, and remain independently collapsible. Duplicate Zendesk ticket 10:33 SGT precedes escalation 10:40 SGT. Returned baseline group counts remain failure 1/1/2/1 and duplicate 2/1/0/3. |

Zero-navigation-evidence-POST behavior is supported by executed component handlers/API tests and unchanged explicit request wiring. Chrome retains the same local request identities through navigation. No browser network trace/HAR was captured; this is not a claim of captured network-level proof.

## Initial executed checks, before code-review fixes

Use Node **22.21.1**, with its bin directory first in PATH. From `frontend/`:

```sh
npm test
npm run typecheck
npm run build
```

- `npm test`: **42 passed, 0 failed/skipped** on 18 November. This includes 29 existing tests, 12 new case-navigation tests and one additional evidence-fragment test.
- `npm run typecheck`: passed (`next typegen && tsc --noEmit`).
- `npm run build`: passed; production compilation, TypeScript and static generation completed. The earlier pre-pause build's process handle was unavailable after resumption, so a fresh build was run successfully on 18 November.
- `git diff --check`: passed.
- No frontend lint script/linter exists; no lint pass is claimed. Backend tests were not rerun for this frontend-only increment.

The new Node tests execute actual component callbacks/effects with deterministic hook scheduling and use actual React static rendering for presentation. They do not simulate the full React DOM/browser lifecycle; the connected Chrome checks separately exercise mounted retention, native disclosures, focus, scrolling, fragments and history.

Executed browser module against the local HTTPS app through the connected Chrome APIs:

```js
await checkWorkspaceRegressions(tab, viewport);
await checkThreadContext(tab);
```

The first function requires explicitly retrieved failure-case evidence. The second requires one local response per seeded case and Payment failures active. Native pointer input avoids the locator's preparatory scrolling when measuring retained positions.

Desktop relationship target top/header bottom: **175.20 / 146.00px** at 1440×900; **173.96 / 144.97px** at 1280×800. Tab/Shift+Tab between Overview/Evidence and direct view-focus retention pass. Compact Overview smoke at 1024×768, 390px and 320px retains amount/progress with page width equal to viewport width. Mobile Evidence entry at 390px/320px retains case identity, amount, four groups and the explicit Inspect evidence action without whole-page overflow.

Review screenshots, outside Git:

- `/private/tmp/opspilot-ux2-overview-1440.jpg`
- `/private/tmp/opspilot-ux2-overview-1280.jpg`
- `/private/tmp/opspilot-ux2-evidence-entry-1280.jpg`

Temporary browser viewport overrides were reset and the verification tab closed. Only the local frontend/backend processes started for the resumed verification were stopped.

## Limits and handoff

- Page-memory retention is intentional. Full reload does not restore previous evidence responses, request lists, disclosure/scroll state, or selected case. Durable backend request history remains separate from the locally displayed list.
- The seeded backend has one case per thread. Same-thread multi-case isolation is exercised with controlled component data, not invented live catalog records.
- No live exceptional-state browser injection, network trace, screen-reader walkthrough, contrast audit, actual text-zoom/reflow acceptance, or WCAG conformance claim. Narrow-width smoke is not UX-4 acceptance; the mobile drawer remains deferred.
- Evidence record readability/progressive disclosure remains the existing UI and belongs to UX-3. Comprehensive responsive/accessibility/regression acceptance remains UX-4. Findings/assistant/review, new backend capabilities and Task 5B remain deferred.
- No commit, push, merge, PR, or Increment 3 work. Recommended next step: owner review of this uncommitted Increment 2 diff and acceptance evidence.

The owner should be able to explain why selection is separate from retrieval, why draft version is not a data-scope identifier, how mounted per-case state and scoped fragments prevent mixing, why an abort cannot cancel server work, and why page-local history is not durable investigation persistence.


## Code-review blocker fixes — 18 November 2026

Scope: only the three owner-reported Medium-severity blockers. This follow-up changes six files already in the uncommitted UX-2 work:

| File | Review fix |
|---|---|
| `frontend/app/investigation-panel.tsx` | Abort parent requests and advance a context generation on invalidation/unmount; fence success, error, completion and child callbacks |
| `frontend/app/case-workspace.tsx` | Framework-compatible fragment/history writes and one authoritative, per-entry scroll-position map with manual restoration |
| `frontend/tests/case-navigation.test.mjs` | Two deterministic delayed-workspace regressions covering lost authorization/state context and legitimate explicit recovery |
| `frontend/tests/workspace-regressions.browser.mjs` | Mounted relationship → view/thread → Back/Forward and direct deep Evidence Back/Forward regressions at both desktop sizes |
| `docs/UX_INCREMENT_2.md` | This review-fix record |
| `docs/PROJECT_STATUS.md` | Current review/verification status |

The rest of the earlier UX-2 diff is preserved. No dependencies, backend/contracts, fixtures, evidence record presentation, optional improvements or Increment 3 work.

### 1. Late workspace GET after invalidation

Invalidation synchronously increments a context-generation counter, aborts/clears outstanding parent operations, and releases the busy state. Each operation captures its starting generation and checks it alongside its abort signal before running success/error/finalization callbacks. Child version/error callbacks also belong to the generation that rendered them. Teardown advances the generation as well.

The delayed-response tests start Reload saved workspace, invalidate through the inspection's public scope-error callback, then resolve the earlier GET successfully. SESSION_EXPIRED keeps protected content removed and the expiry explanation intact. STALE_STATE permits an explicit reload, and the older GET cannot overwrite the recovered state. An ineffective-abort variant proves the generation fence works independently of cancellation. Explicit incident entry/create/resume after legitimate session recovery remains usable. No callback from the old operation can render CaseWorkspace and restart its case loading.

### 2. Relationship fragments and browser history

The installed Next.js history integration was inspected locally. The workspace now passes only its own metadata through the public `pushState`/`replaceState` APIs. It does not inspect, reconstruct, or name private router keys. Relationship activation keeps the native anchor URL and existing expansion/focus handler, while the workspace intercepts the default hash-history write and creates a framework-compatible entry associated with the selected case/view. Modified clicks retain their normal browser behavior.

Back/Forward also handles fragment-only entries. A returning target is revealed and its summary focused; if its retained position would leave that focus outside the viewport or behind the incident header, it scrolls into view. Other records remain expanded. No retrieval occurs during these transitions.

### 3. Evidence position on direct browser Forward

The position map in page memory is the only scroll-position store. History metadata contains an entry ID and scoped location, with no competing `y` snapshot. A per-location index identifies the most recently visited entry when returning through workspace controls. Scroll events and explicit departures update the same map, including departure through browser Back. Restoration suppresses intermediate layout scroll updates.

While mounted, the workspace selects `history.scrollRestoration = "manual"` so native restoration cannot race application restoration. Cleanup restores the previous browser setting and removes listeners. Direct Back → Overview → Forward now restores the departing Evidence entry's recorded position, without requiring an intervening workspace-button click.

### Executed review checks

Node **22.21.1**, from `frontend/`:

```sh
node --test --test-name-pattern='delayed workspace GET|late successful reload' tests/case-navigation.test.mjs
npm test
npm run typecheck
npm run build
```

- Focused delayed-response regressions: **2 passed** (including cancellation-effective/ineffective variants and explicit recovery).
- Complete frontend suite: **44 passed, 0 failed/skipped**.
- TypeScript and optimized production build: passed. After restoring the generated Next.js declaration file to its checkpoint content, direct `tsc --noEmit` also passed.
- `git diff --check`: passed. Backend/contracts, dependency/lockfiles and approved specifications remain unchanged. The generated `next-env.d.ts` change was restored; it is not part of the review-fix diff.

Mounted Chrome, local HTTPS app, existing APIs and explicitly retrieved evidence:

```js
await checkReviewHistoryRegressions(tab, viewport);
await checkWorkspaceRegressions(tab, viewport);
await checkThreadContext(tab);
```

| Viewport | Relationship → Overview/thread → Back/Forward | Direct duplicate Evidence Back/Forward |
|---|---|---|
| 1440×900 | Correct case/view/fragment; target expanded and focused, top **162.11px**, header bottom **146.00px**; both responses/request IDs retained | **2125.5px → 2125.5px**, two cycles; both Zendesk records remain expanded |
| 1280×800 | Correct case/view/fragment; target expanded and focused, top **161.08px**, header bottom **144.97px**; both responses/request IDs retained | **1925.5px → 1925.5px**, two cycles; both Zendesk records remain expanded |

The retained panels and exact request identities demonstrate that these traversals did not reload the document or trigger fresh inspection. These are UI observations, not a network trace/HAR. No private Next.js router-state assumptions appear in the regression assertions.

Existing relationship pointer/Enter expansion, independent collapse, originating-record retention, visible focus, fragment URLs, Overview/Evidence Tab/Shift+Tab order and thread-context retention pass at the desktop targets. Full reload still returns Payment failures → Overview/no case with no retained Evidence panels. No-case Evidence and keyboard Go to Overview retain correct focus and explicit selection/retrieval boundaries.

Screenshot: `/private/tmp/opspilot-ux2-review-relationship-back-1280.jpg`. Viewport override reset, verification tab closed, and only the temporary frontend/backend processes started for this follow-up stopped.

### Remaining limitations

The authorization race is deterministically exercised through actual component handlers/effects, not a forced live-session expiry in Chrome. Chrome history/scroll checks exercise the mounted framework and native navigation; other browsers, screen readers, contrast and zoom audits remain unverified. The original page-memory/full-reload boundary remains intentional. No WCAG conformance, backend test rerun, or independent re-review approval is claimed.

No commit, push, merge, PR, or Increment 3. Recommended next step: owner re-review of these three fixes.


## Independent-QA P2 focus fix — 19 November 2026

Independent QA reported FAIL because keyboard return to retained Evidence restored the scroll offset but left focus on the now-offscreen Evidence tab. This follow-up fixes only that blocker; it does not establish independent-QA acceptance.

### Changed files

| File | Bounded change |
|---|---|
| `frontend/app/case-workspace.tsx` | Repair focus after a keyboard Overview → retained Evidence transition when the triggering tab becomes offscreen |
| `frontend/app/globals.css` | Visible focus outline for a temporary programmatic text destination inside Evidence |
| `frontend/tests/case-navigation.test.mjs` | Four focus-destination, stale/missing/hidden record, fallback, modality and newer-focus regressions |
| `frontend/tests/workspace-regressions.browser.mjs` | Exact QA reproduction at both desktop viewports, scroll/focus/state assertions, native Tab/Shift+Tab and pointer checks |
| `docs/UX_INCREMENT_2.md` | This fix/verification record |
| `docs/PROJECT_STATUS.md` | Current independent-QA follow-up status |

The existing uncommitted UX-2 work is preserved. No backend, dependency, fixture, evidence record presentation, unrelated navigation, Git publication or Increment 3 change.

### Behavior

Keyboard activation is identified from the focused workspace tab's `:focus-visible` state. The coordinator carries that initiating element only for Overview → Evidence with a selected case. It restores the existing per-entry scroll position first, then transfers focus only if that same tab still holds keyboard focus and is no longer visible. Pointer interactions, unrelated transitions, onscreen tab focus, and a newer user focus action do not invoke the repair.

The destination is resolved from the selected case's currently rendered Evidence rather than a saved record handle. A fully visible native control is preferred. Disconnected, hidden, closed-disclosure and header-obscured candidates are skipped. If the old record is unavailable, current readable content provides a fallback, including visible long payload content when necessary. Noninteractive fallback content receives a temporary `tabindex="-1"`, removed on blur, plus a visible outline; it does not become a permanent Tab stop. Every repair uses `focus({ preventScroll: true })` and leaves the scroll map/history mechanism unchanged. Native sequential navigation resumes from the destination's document position.

### Exact mounted reproduction: failure before the fix

Executed: select CASE-DUP-001 → explicitly inspect → expand both Zendesk records → Overview → reopen case → scroll deeply → browser Back → native Tab to Evidence → Enter. The regression reproduced both QA measurements before the application change:

| Viewport | Retained scroll | Focused tab top before fix |
|---|---|---|
| 1440×900 | 2125.5px | −1704.99px, outside the viewport |
| 1280×800 | 1925.5px | −1506.02px, outside the viewport |

### Verification after the fix

```js
await checkRetainedEvidenceKeyboardFocus(tab, viewport);
```

| Viewport | Expected / actual scroll | Restored keyboard focus |
|---|---|---|
| 1440×900 | **2125.5 / 2125.5px** | `SYN-ZD-TICKET-002` summary, top **273.29px**, bottom **305.29px**, below header bottom **146px** |
| 1280×800 | **1925.5 / 1925.5px** | Same summary, top **472.26px**, bottom **504.26px**, below header bottom **144.97px** |

At both sizes the destination is inside the active Evidence panel with visible keyboard focus. Native Tab and Shift+Tab follow document order; pointer return keeps pointer focus without transferring it into Evidence. Both Zendesk records stay expanded, and exact response/request identities are unchanged.

The existing `checkReviewHistoryRegressions`, `checkWorkspaceRegressions` and `checkThreadContext` also pass: direct native Back/Forward preserves positions, relationship fragments restore the correct case/view and open/focus their target, originating records remain open, source results remain local, and Overview/Evidence keyboard order is retained. These are mounted Chrome checks through the connected browser, not simulated DOM assertions.

From `frontend/`, Node **22.21.1**:

```sh
node --test --test-name-pattern='retained Evidence|missing record focus|long visible Evidence' tests/case-navigation.test.mjs
npm test
npm run typecheck
npm run build
```

- Focused component/helper regressions: **4 passed**.
- Full frontend suite: **48 passed, 0 failed/skipped**.
- TypeScript and production build: passed.
- The generated `next-env.d.ts` reference change was restored; direct `tsc --noEmit` after restoration also passed.
- `git diff --check` and the bounded before/after application diff checks passed. No backend tests or lint tooling are claimed.

### Evidence request count and artifacts

A temporary backend process used access logging during this bounded synthetic verification. Across the before/after focused runs, screenshot reproduction and existing navigation regressions, the log contains exactly **two evidence POSTs**, matching the explicitly initiated duplicate-case and failure-case inspections. There are **zero unintended evidence retrieval requests** from navigation, focus repair, record expansion or history traversal. The duplicate-only focused window contains just its one setup inspection. No automatic retry, source refresh or findings call was added.

- Access log: `/private/tmp/opspilot-ux2-qa-focus-access.log` (request methods/paths/statuses only; no credentials/headers/bodies).
- Focus screenshot: `/private/tmp/opspilot-ux2-qa-focus-1280.jpg`.

Viewport override reset, verification tab closed, and only the frontend/backend processes started for this follow-up stopped.

### Remaining limits and handoff

Missing/removed destination, long-content fallback and deferred-focus cancellation branches use controlled unit tests; the seeded records were not removed or mutated for browser testing. Screen readers, other browsers, contrast/zoom audits and comprehensive UX-4 acceptance remain unverified. No independent-QA pass or WCAG conformance is claimed. Page-local retention and full-reload boundaries are unchanged.

No commit, push, merge, PR or Increment 3. Stop for owner re-review of this single P2 fix.


## Final acceptance and checkpoint authorization — 19 November 2026

The owner reports that Increment 2 passed final Code Review and independent QA, including all recorded fixes. The subsequent instruction authorizes creating and pushing a checkpoint only after branch, parent, complete file inventory, content/sensitive-data and staged-diff verification.

Verified branch: `codex/task-5ux-workspace-redesign`. Verified local HEAD and existing remote feature-branch tip before checkpoint creation: `df038a827aaf54a80448789fb8bb30df65946788` (approved UX-1 parent). The checkpoint contains the 13 frontend/test/documentation files listed above. Source content remains the QA-approved implementation; only documentation is updated to record acceptance and checkpoint authorization. Generated files, local configuration, credentials, screenshots/logs, backend/dependencies and unrelated changes are excluded.

Authorized commit message: `feat(ux): add case navigation and retained evidence state`. Publication is limited to the existing remote feature branch, after staging verification and `git diff --cached --check`. This checkpoint procedure does not rerun tests or replace the actual verification evidence and limitations above. No PR, merge, branch deletion, application code change or Increment 3.
