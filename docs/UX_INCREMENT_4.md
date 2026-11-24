# Task 5-UX — Increment 4 verification

Implemented on 22–23 November 2026. **The owner reports independent Code Review and final QA passed, including re-verification of the resolved P2 hover-contrast defect, and authorizes only the verified Increment 4 Git checkpoint.** See [final acceptance and checkpoint authorization](#final-acceptance-and-checkpoint-authorization--23-november-2026). Earlier QA failure/recheck language below is historical. Owner-reported manual checks and independently observed results remain distinct; no full WCAG conformance is claimed. No PR, merge, branch deletion or Task 5B.

## Owner-reported manual accessibility checks — 23 November 2026

The owner reports **PASS for all four manual checks**, confirmed in response to the four-item acceptance question: the spoken Payment failures journey, the spoken Possible duplicates journey, loading/error announcements, and separate 200% text-only scaling. Detailed observations, browser/screen-reader versions, and the scaling method have not been supplied. These are owner-reported passes, not independently observed passes or a full WCAG conformance claim. Historical statements below that these checks were untested describe the earlier agent verification boundary; the agent has not acquired spoken-audio verification capability.

| Manual check | Owner-reported result | Independent observation |
|---|---|---|
| VoiceOver — Payment failures journey | PASS | UNTESTED: no spoken-audio capture available |
| VoiceOver — Possible duplicates journey | PASS | UNTESTED: no spoken-audio capture available |
| VoiceOver — loading/error announcements | PASS | UNTESTED: structural live-region checks do not prove spoken timing/repetition |
| Separate 200% text-only scaling | PASS | UNTESTED: browser/version and scaling method not supplied; no separate text-only scaling performed by the agent |

## Final independent QA — 23 November 2026

Baseline: approved UX Blueprint, D-030–D-034 and both threads' amended Overview/Evidence specifications. Earlier implementation verification below is historical; this section records the subsequent independent run. Only this report and Project Status were edited. Hash comparison of 79 non-document repository files found no application/test/fixture/configuration changes during QA.

Environment: macOS 27.2.1; Chrome 157.0.8103.79; existing local HTTPS frontend, FastAPI and PostgreSQL. Browser modules ran through the connected Chrome APIs. No independent spoken screen-reader output or text-only scaling is claimed. Native Chrome page zoom is distinct from text-only scaling. Safari was not repeated after the earlier certificate-warning boundary and the owner's instruction to leave it untested.

| Acceptance area | Independent result | Evidence / boundary |
|---|---|---|
| UX-R18 responsive layouts | PASS | Both threads' Overview and retained Evidence at 1440×900, 1280×800, 1024×768, 390×844 and 320×568: 20 checked presentations, no whole-page horizontal overflow. Mobile Overview uses one column. Both Evidence views retain four groups/six outcomes and all five/six returned records. |
| Mobile modal navigation | PASS | At 390/320: named native modal, initial Close focus, forward/reverse Tab containment, Escape/Close return. Thread selection updates cases; case selection dismisses the modal and focuses case context. Crossing into desktop dismisses modality and focuses visible rail navigation. Both mobile evidence relationship keyboard journeys passed. |
| UX-R19 keyboard and focus behavior | PASS | Native Tab/Shift+Tab/Enter entry/resume, no-selection Evidence/Go to Overview, both case selections/inspections, source collapse/reopen, record/technical disclosure expansion, relationships and independent collapse. Pointer and Enter relationship regressions passed at both desktop sizes with targets below the sticky header. Retained Evidence keyboard focus is visible and preserves scroll, native Tab order and pointer behavior. |
| UX-R19 spoken screen-reader behavior | UNTESTED | Independent spoken testing remains unavailable. Owner reports PASS for both journeys and announcements, as recorded separately above. Reading order, speech timing and absence of whole-tree repetition are not independently established by accessibility-tree output. |
| UX-R20 page zoom / reflow | PASS | Chrome's native toolbar reported 200% and 400% using Command+= in the selected QA tab. Resulting CSS viewports 720×361 and 360×180; no horizontal page overflow, static incident header and accessible mobile navigation. Separate 320 CSS-pixel checks cover both cases and both views. |
| UX-R20 separate text-only scaling | UNTESTED | Owner-reported PASS only; independent method/result not available. Browser limitations are not recorded as WCAG failures. |
| UX-R20 contrast | FAIL | P2 below: normal text in hovered inactive thread controls and Overview case rows falls below the Blueprint's 4.5:1 requirement. Earlier/default-state samples ≥5.50:1 did not cover this interaction state. |
| UX-R20 target sizes / semantics | PASS, bounded | Desktop/mobile sampling: one main landmark, no duplicate IDs or unnamed visible controls, no sampled applicable non-inline control below 24×24 CSS pixels; minimum sampled height 28px. Native disclosures, named source lists, selected/current navigation and disabled Findings remain exposed. No complete accessibility-engine audit is claimed. |
| UX-R20 reduced motion | UNTESTED at OS preference level | Reduced-motion CSS rule inspected; OS preference was not toggled. |
| UX-R21 automated verification | PASS | Node 22.21.1: `npm test` 66 passed, zero failures/skips; `npm run typecheck`; `npm run build`; syntax checks on all three browser modules; `git diff --check`. No backend rerun, lint pass or live-model evaluation. |
| UX-1 / entry, shell and reload regressions | PASS | Explicit session reuse, incident preview and create/resume; no-case boundary; Go to Overview restores Overview focus. Fresh owned URL and full reload after retrieval default to Payment failures → Overview/no active case with zero retained evidence panels. Findings stays unavailable. |
| UX-2 / state, history and scroll regressions | PASS | Exact request identities and independent record expansions retained through thread/view switches and Back/Forward. Repeated Forward restored 3694→3694px at 1440 and 1933.5→1933.5px at 1280. Retained keyboard Evidence return restored 2133.5→2133.5px and 1933.5→1933.5px with visible focus. |
| UX-3 / evidence, limitations and relationships | PASS | All 11 returned payloads match the frozen fixture. Counts failure 1/1/2/1 and duplicate 2/1/0/3; provider extracts remain one record. Independent Loki/Tempo zero outcomes, local provider completeness/bank gaps, original minute precision/provenance, technical disclosures, one duplicate caution and Zendesk 10:33-before-10:40 chronology preserved. No inferred payment verdict or progress change. |
| Live error and explicit recovery | PASS | Stopping only the temporary backend produced evidence alert/Retry and count unknown in all groups, plus a connection-unavailable alert after Check again. Restart and explicit evidence Retry succeeded. Missing incident alert is associated through `aria-describedby` and preserves valid evidence. |
| Loading / authorization / stale / exceptional-source states | PASS in controlled tests | Existing component/controller/parser tests execute busy activation guards, one atomic retrieval status, unknown loading counts, failed/partial/interrupted/availability distinctions, authorization invalidation, late-response fences and explicit stale-version retry. Real browser session expiry/cross-owner denial and forced partial-source responses remain UNTESTED in this run; no database/authentication mutation was used. |
| Request side effects | PASS | Backend access log contains exactly three successful evidence POSTs: the two explicit seeded inspections and one explicit recovery inspection. Two deliberate downtime activations failed at workspace preflight, before evidence POST. Navigation/layout/disclosures/history/reloads added no evidence POSTs; zero Findings calls. |

### Merge-blocking defect — P2: hover backgrounds make navigation and case text unreadable

File references: `frontend/app/globals.css:16` (generic hover rule), `:59` (thread hover), `:188` (case-row hover).

Reproduce on Chrome at 1440×900, 100% zoom:

1. Open a seeded investigation. Hover an inactive thread button. A deterministic reproduction is to click Payment failures, leave the pointer there, then activate Possible duplicates with the keyboard.
2. Payment failures remains hovered but inactive. Computed background is `#1948ad`; label color is `#46566b`, at **1.09:1** for 13px text.
3. Open Overview and hover its case row. A deterministic reproduction is to click the row and then activate Overview with the keyboard without moving the pointer. The row background is `#1948ad`; case/action text `#214fae` measures **1.09:1**, muted field labels **1.36:1**, and inherited row text **1.69:1**.

The generic `button:hover:not(:disabled):not([aria-disabled="true"])` has higher specificity than the intended thread and case-row hover rules, so its dark primary-button background wins while those controls retain dark text. This violates UX-R20's normal-text contrast requirement. This is a reproduced interaction-state defect, not an inference from missing browser functionality or a full WCAG audit. No implementation fix was made. Recommend limiting the primary-button hover rule or giving each affected control an intentional hover treatment, then rechecking these states and the existing keyboard/drawer behavior.

Temporary evidence outside Git:

- `/private/tmp/opspilot-ux4-final-hover-contrast.jpg` — inactive thread hover.
- `/private/tmp/opspilot-ux4-final-case-hover.jpg` — Overview case-row hover.
- `/private/tmp/opspilot-ux4-final-results.json` — browser observations.
- `/private/tmp/opspilot-ux4-final-backend.log` — method/path/status request accounting; no headers or credentials.
- `/private/tmp/opspilot-ux4-final-tests.log`, `-typecheck.log`, `-build.log` — completed automated check output.

One temporary browser tab was cleaned up when the owner sent “continue”; its subsequent recovery action could not run in that tab. The fresh owned URL correctly resumed defaults; the evidence-error/restart/explicit-Retry sequence was then repeated to completion. Earlier observations are retained, not counted as a completed action after cleanup. Native tab shortcut attempts initially did not change zoom; only the later native Chrome toolbar-confirmed 200%/400% observations count as page-zoom evidence.

**Final verdict: FAIL / not ready for acceptance or merge until the P2 hover-contrast defect is fixed and rechecked.** Owner-reported manual passes do not override this independent failure. Remaining evidence limits are independent spoken/text-only testing, missing manual environment/observation details, OS-level reduced-motion testing, live authorization/partial-source failure testing and cross-browser coverage. No WCAG 2.2 AA conformance claim. Stop; no implementation, commit, push, merge, PR or Task 5B.

## P2 hover-contrast fix — 23 November 2026

The owner's follow-up authorizes only the reproduced contrast blocker. Reproduced both defects before editing the application: hovered inactive thread label **1.0903:1**; hovered case-row link/identity **1.0865:1**, muted labels **1.3551:1**, and ordinary row text **1.6899:1**. The new browser checker correctly rejected both observations, with actual `:hover` confirmed.

### Root cause and exact correction

The generic selector `button:hover:not(:disabled):not([aria-disabled="true"])` has specificity **(0,3,1)**. It overrode `.thread-nav button:hover` **(0,2,1)** and `.case-row:hover:not(:disabled)` **(0,3,0)** despite appearing earlier in the stylesheet. Its dark `#1948ad` primary-button background therefore paired with the components' dark foregrounds. Adding the busy-state exclusion in Increment 4 increased this selector's specificity; the original contrast sampling missed hovered states.

Only the generic selector changed:

```css
/* Keep primary hover below component variants and their selected states. */
button:where(:hover:not(:disabled):not([aria-disabled="true"])) { background: #1948ad; }
```

`:where()` makes the conditions contribute zero specificity, leaving **(0,0,1)** for the generic rule. Existing thread/case/tab styles and their selected-state rules now win. Native/ARIA disabled exclusions and the blue primary hover remain. No palette, spacing, component markup, state, request or backend change. See [MDN's specificity explanation](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:where).

### Changed files in this follow-up only

| File | Change |
|---|---|
| `frontend/app/globals.css` | One hover selector and its explanatory comment |
| `frontend/tests/responsive-accessibility.browser.mjs` | Computed text/ancestor-background contrast sampling for an individual control, real pseudo-class observations and unrounded 4.5:1 assertions |
| `frontend/tests/hover-contrast.test.mjs` | Three focused checker regressions: reject QA ratios and 4.4999, require measured text/actual interaction states, distinguish disabled from enabled-but-unselected controls |
| `docs/UX_INCREMENT_4.md`, `docs/PROJECT_STATUS.md` | Preserve independent QA history and record this fix, measurements and recheck boundary |

The worktree already contained the full uncommitted Increment 4 implementation. A pre-fix content inventory was saved outside Git; this follow-up changes only the five files above. The generated `next-env.d.ts` was restored after build/type generation.

### Mounted Chrome results

Real pointer and native keyboard actions checked **1440×900, 1280×800 and 390×844**, using the live HTTPS application and existing synthetic investigation. Mobile thread measurements use the actual modal drawer. Both seeded Overview rows were exercised; no evidence inspection was needed.

The saved results contain **44 passing control-state observations**. Default/unselected, selected, focus-visible, hover, hover+focus-visible and selected+hover+focus-visible states were checked where applicable. The set covers threads and case rows, native disabled Findings, a case-navigation default and the primary Close button. Desktop and mobile selections continue to use the existing handlers. These are bounded interaction checks, not a rerun of every Increment 4 journey or all WCAG criteria.

| Computed text/background | Corrected ratio |
|---|---:|
| Inactive thread label: `#46566b` on hover `#e9eef6` | **6.43:1** |
| Thread count: `#46566b` on `#e6eaf0` | **6.20:1** |
| Selected thread label: `#214fae` on `#eaf0fc` | **6.57:1** |
| Selected thread count: `#214fae` on `#d8e4fd` | **5.88:1** |
| Default row muted labels: `#566477` on white | **6.03:1** |
| Hovered/selected row muted labels: `#566477` on `#f4f7fc` | **5.61:1** |
| Hovered/selected row identity/action: `#214fae` on `#f4f7fc` | **7.00:1** |
| Hovered/selected row ordinary text: `#202e3e` on `#f4f7fc` | **12.85:1** |
| Hovered/selected row limitation: `#71501e` on `#f4f7fc` | **6.82:1** |
| Disabled Findings: `#647084` on white, default and hover | **5.01:1** |
| Primary Close: white on `#245bce` / hovered `#1948ad` | **6.06:1 / 8.17:1** |

Displayed ratios are rounded only for reporting; assertions compare raw ratios to 4.5. Lowest enabled text ratio across these observations is **5.6117453497:1**. Hovered thread-label raw ratio is **6.4287903959:1**. Native disabled controls are exempt from SC 1.4.3, but their default/hover colors were also recorded and unchanged. Enabled unselected navigation is not exempt. See [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

Selected thread borders remain `#d2def5`; selected case rows keep their blue 3px inset marker. Every sampled focus-visible state retains its 3px solid `#a45400` outline. Primary hover still darkens blue; case and thread hover use their existing pale backgrounds. Visual screenshots confirm the established dashboard design.

The checker records real `hover`, `focusVisible`, `selected` and `disabled` states. A selector initially matched a retained hidden case, and two combined-state attempts moved the pointer out of the row when locator preparation scrolled the page; those attempts failed their visibility/state preconditions and were not counted as passing hover checks. Retargeting the active row and using native Tab input produced the recorded combined-state observations. No pseudo-state forcing, CSS injection or application-state inspection was used.

### Automated verification and limits

Node **22.21.1**, with its bin directory first in PATH, from `frontend/`:

```sh
npm test
npm run typecheck
npm run build
./node_modules/.bin/tsc --noEmit
node --check tests/responsive-accessibility.browser.mjs
node --check tests/hover-contrast.test.mjs
```

- **69 tests passed, 0 failed/skipped** (66 retained plus three focused checker regressions).
- TypeScript and production build passed; direct TypeScript passed after restoring the generated declaration to its pre-fix contents.
- Changed-module syntax and `git diff --check` passed.
- Backend access output: **zero evidence POSTs, zero findings calls**. Only explicit session/investigation resume and scoped case/workspace GETs were used.
- Temporary frontend/backend processes stopped; viewport override reset and agent-created tab closed. No dependencies, backend files/contracts, commits, pushes, merges, PRs or Task 5B.

Artifacts outside Git: `/private/tmp/opspilot-ux4-p2-contrast-results.json`, `/private/tmp/opspilot-ux4-p2-access.log`, and screenshots `/private/tmp/opspilot-ux4-p2-thread-hover-1440.jpg`, `/private/tmp/opspilot-ux4-p2-case-hover-1440.jpg`, `/private/tmp/opspilot-ux4-p2-hover-mobile.jpg`.

No remaining contrast failure was observed in this bounded check. The pre-existing browser-extension hydration warning about Grammarly-added body attributes appeared again; no unrelated workaround was added. Other browsers, spoken output, OS reduced-motion and comprehensive interaction/conformance testing were not repeated. Owner-reported manual checks and independent-verification limits above remain distinct. **Ready for independent P2 recheck; this implementation verification does not replace the historical independent QA FAIL with a new independent acceptance.** Stop after reporting this fix.

## Starting checkpoint and scope

Before editing, verified:

- Branch: `codex/task-5ux-workspace-redesign`.
- HEAD: `5e9ee8d4de2d4e76a595cd563b22b8e169ce54cc`.
- `git status --short`: empty.

Read the repository instructions, implementation prompt, project brief/learning plan/status, decision log, approved UX Blueprint, and both threads' Overview/Evidence specifications. D-030–D-034 and Blueprint UX-R18–R21 govern this increment. The owner's current implementation instruction supersedes older documentation-only/checkpoint stop instructions.

Only frontend responsive/accessibility work, focused regressions, and project documentation changed. Backend, API contracts, frozen fixtures, dependencies, storage and evidence selection are unchanged. Findings, assistant, live OpenAI, human review and export remain deferred.

## Changed files

| File | Purpose |
|---|---|
| `frontend/app/workspace-shell.tsx` | Native mobile modal drawer, shared navigation, initial focus, Tab containment, Escape/Close return, case-selection dismissal and desktop-breakpoint cleanup |
| `frontend/app/globals.css` | Single-column mobile case rows, wrapping, drawer styling, larger controls, focus clearance, bounded session/rail height, reduced-motion rule and input-border contrast |
| `frontend/app/case-workspace.tsx` | Exclude every closed disclosure ancestor when choosing a retained-Evidence focus destination |
| `frontend/app/evidence-view.tsx` | One persistent atomic retrieval status, source-named record-list disclosures, focusable busy inspection with guarded activation |
| `frontend/app/investigation-panel.tsx` | Error description associated with incident input; read-only busy input and guarded, focusable busy actions |
| `frontend/app/visitor-session-panel.tsx` | Guard busy activation while keeping the session button focusable |
| `frontend/app/page.tsx` | Explicit skip-link focus destination |
| `frontend/tests/workspace-shell.test.mjs` | Actual drawer handlers: naming/opening, Tab boundaries, resize/close cleanup, preserving later focus and case dismissal |
| `frontend/tests/evidence.test.mjs` | Single status region, source disclosure names and guarded focusable busy inspection |
| `frontend/tests/case-navigation.test.mjs` | Nested closed-record focus exclusion; busy session activation/error recovery; retain the existing invalidation assertion with `aria-disabled` |
| `frontend/tests/workspace-regressions.browser.mjs` | Correct native Tab eligibility prediction for descendants of closed disclosures |
| `frontend/tests/responsive-accessibility.browser.mjs` | Reusable connected-Chrome layout, drawer, bounded accessibility and rendered-text contrast checks |
| `docs/PROJECT_STATUS.md`, this report | Current implementation, verification evidence, remaining gaps and stop boundary |

The drawer uses native `showModal()` so background content is inert. An explicit Tab boundary loop keeps focus inside navigation. Native Escape and Close restore the invoker; case activation closes the modal before the existing selection callback focuses case context. Switching threads within the drawer updates its case list. Crossing into desktop closes the modal and focuses visible desktop navigation. No evidence panel is remounted by resizing.

Busy actions use `aria-disabled` plus activation guards. This matters because native disabling of the focused session button was observed to move focus to the body during requests. Existing evidence-controller and session-request guards remain in place. A native keyboard rerun confirmed session, preview and inspection actions retain focus while awaiting their results. The successful create/resume action removes its button; the next native Tab reaches the first thread control.

## Acceptance evidence

| Criterion | Result and boundary |
|---|---|
| UX-R18 | Passed in Chrome at 1024×768, 390×844 and 320×568, plus both desktop sizes. Mobile navigation replaces the rail. Drawer initial focus, both Tab boundaries, Escape, Close, current-case selection and desktop resizing were checked. Amount/currency, payment context, progress, source headings and limitations remain available. No whole-page overflow observed. |
| UX-R19 | Both seeded keyboard journeys completed, including explicit session reuse, preview/create-resume, case selection, inspection, source/record expansion and relationship navigation. Native accessibility-tree walkthrough confirmed names, headings, selected states, disclosure states, source text and limitations. **Spoken screen-reader walkthrough remains untested**; this criterion is not fully signed off. |
| UX-R20 | Sampled text contrast, essential input/focus contrast, target dimensions, motion behavior, actual Chrome 200%/400% page zoom and 320 CSS-pixel reflow checked. **Separate 200% text-only zoom and other browser/assistive-technology combinations remain untested.** No full-AA claim. |
| UX-R21 | 66 frontend tests, TypeScript and production build passed under Node 22. Both Task 4B focused browser regressions repeated: relationship target reveal/focus and duplicate Zendesk chronology. Broader entry/resume/reload/error, responsive, retained-focus and history checks passed. Backend results remain historical. |
| Earlier UX-R01–R04, R07, R17 | Explicit entry/resume, default Payment failures → Overview/no selected case, no-selection Evidence boundary, Go to Overview focus and full reload checked. Findings remains disabled/unavailable; no findings calls. At desktop Evidence entry, case/action/first source fit below the single sticky incident header. |
| Earlier UX-R05–R06, R09, R13–R16 | Both cases, exact money/source payloads, original timestamps/provenance, independent disclosures, relationship traversal, request identities, thread/view retention and browser history retained. Counts remain failure 1/1/2/1 and duplicate 2/1/0/3. Review stays Not started. |
| Earlier UX-R08, R10–R12 | Existing and added controlled tests retain authorization invalidation, late-response isolation, explicit stale-version retry, loading/error/empty/zero-match/partial/unavailable/failed/interrupted and not-included/not-constructed distinctions. These exceptional source/auth conditions were **not forced against the live browser backend**. |

## Automated verification

From `frontend/`, with `/Users/iampankajk/.nvm/versions/node/v22.21.1/bin` first in PATH:

```sh
npm test
npm run typecheck
npm run build
```

- Node **22.21.1**; **66 tests passed, 0 failed/skipped**. The approved checkpoint had 58 tests; eight focused regressions were added.
- TypeScript passed: `next typegen && tsc --noEmit`.
- Production build passed, including TypeScript and static generation.
- The generated `next-env.d.ts` was restored to its checkpoint contents; direct `tsc --noEmit` passed afterward.
- Browser-module syntax checks and `git diff --check` passed.
- No frontend lint script/linter exists. No lint pass, backend rerun, dependency installation or live-model evaluation is claimed.

The Node tests execute actual component render branches/handlers with the existing deterministic harness. They do not prove native focus/scroll/assistive-technology behavior; Chrome observations supply the bounded evidence below.

## Browser verification

Connected Chrome used the real local HTTPS frontend and existing FastAPI/PostgreSQL backend. The development certificate was already usable; no certificate/security setting was changed. Temporary processes were stopped afterward, the viewport override reset, page zoom reset to 100%, and the agent-created tab closed.

| Check | Observed result |
|---|---|
| Target widths | Overview and both seeded Evidence presentations checked at 1440×900, 1280×800, 1024×768, 390×844 and 320×568. No page overflow; mobile case fields use one column, evidence fields wrap/stack. |
| Evidence fidelity | All five failure and six duplicate payloads match the unchanged fixture. Four groups/six outcomes remain. Provider extracts remain one record each. Original JSON is closed by default and keyboard inspectable. |
| Source semantics | Duplicate Loki and Tempo each show zero matches. Provider completeness and bank/settlement gaps remain beside provider evidence. No payment verdict or review progress change. |
| Chronology | Duplicate Zendesk ticket 10:33 SGT precedes its 10:40 SGT escalation; support lookup remains in its original source. |
| Desktop relationship target | Pointer and Enter reveal the provider group/record, preserve origin expansion and focus its summary. At 1440: summary 163.09–275.59px, header bottom 146px. At 1280: summary 162.06–274.56px, header bottom 144.97px. |
| History/scroll | Repeated Back/Forward restores request identities and both expanded Zendesk records. Final deep positions: 2133.5 → 2133.5px at 1440; 1933.5 → 1933.5px at 1280. Relationship fragments also restore reveal/focus. |
| Retained keyboard focus | Overview → retained Evidence preserves those positions and visibly focuses live Evidence. Native Tab/Shift+Tab and pointer behavior pass at both desktop sizes. Closed nested summaries are excluded as destinations. |
| Mobile drawer | 390/320: named native modal, focus starts on Close, Shift+Tab reaches last case, Tab wraps to Close, Escape/Close return to invoker. Thread selection updates cases; selection closes and focuses the correct case heading. Desktop resizing releases modality and focuses visible rail navigation. |
| Keyboard-only journeys | Native Tab/Shift+Tab/Enter completed session reuse → incident preview → owned resume → failure selection/inspection → relationship, then duplicate thread/case/inspection → relationship. Busy operation focus stays on its action. Both mobile relationship journeys also pass. |
| Desktop density/stickiness | Sticky incident header at 1440/1280; static at 1024/mobile. Sample 1440 Evidence entry: case top 160.01px; inspection action 351.59–395.59px; first source heading 436.59–478.59px below header bottom 146px. No sticky sources/records/toolbars. |
| Real page zoom | Native Chrome toolbar confirmed 200% and 400%. With normal 1440px window: 200% gives 720×361 CSS pixels; 400% gives 360×180. Header is static, no horizontal page overflow; case context/navigation/actions remain available through vertical scrolling. Separate viewport checks cover 320 CSS pixels, the reflow width equivalent to 1280px at 400%. |
| Errors/reload | Missing incident shows an alert associated with the input, retains two existing local panels and has no 320px overflow. Deliberately stopping only the temporary backend shows connection-unavailable with explicit retry; restarting and Check again recovers. Full reload restores owned workspace at default/no-case with zero retained response panels and no evidence POST. Go to Overview returns focus to Overview. |

Browser modules were run through documented connected-browser APIs. Some test-driver attempts required correction: module reloading used temporary file copies because the runtime caches imports; a combined final batch timed out and was repeated in shorter completed calls. An earlier evidence check expected Evidence when thread memory correctly restored Overview; its precondition was corrected. These attempts are not reported as passing checks.

### Accessibility findings and limits

- **Fixed:** incident input boundary was approximately 2.90:1 against white; changed to `#748399`, approximately **3.85:1**. Focus outline `#a45400` is approximately **5.46:1** against white.
- **Fixed:** native disabled busy buttons dropped keyboard focus. Focusable `aria-disabled` controls now guard repeat activation; controlled regressions and native session/inspection checks pass.
- **Fixed:** geometry alone included hidden nested disclosures in predicted Tab order. Both the focus helper and browser test now account for every enclosing closed disclosure.
- Rendered opaque-background text sampling found **no pair below 4.5:1**; lowest sampled pair was **5.50:1**. Includes muted/status/link/caution text in inspected entry, evidence and drawer states. This is a bounded contrast check, not a complete automated accessibility audit.
- Inspected DOM: one main landmark, no duplicate IDs, no unnamed visible controls, no non-inline target below **24×24px**. Smallest sampled non-inline height was **28px** (brand); primary buttons and mobile evidence disclosures/relationship controls meet the intended 44px height. Inline links use their text context.
- Native accessibility output exposes source-named record lists, expanded/collapsed records, association descriptions on links, source statuses/limitations and named navigation. One visible atomic evidence status region avoids six concurrent loading announcements. Actual spoken announcement timing/order was not tested.
- No animation, transition or smooth scrolling was detected in the inspected main UI; an explicit reduced-motion CSS rule is present. OS-level reduced-motion preference was not toggled/emulated.
- No VoiceOver/NVDA/JAWS spoken walkthrough, Safari/Firefox/mobile-device test, separate text-only zoom or comprehensive automated accessibility engine scan was performed. **UX-R19 and UX-R20 retain these verification gaps. Full WCAG 2.2 AA conformance is not established.**

Verification interpretation follows the [W3C modal-dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), [reflow guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) and [24 CSS-pixel minimum target guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html). These references do not certify this implementation.

### Request accounting and artifacts

Captured backend access output contains exactly **four evidence POSTs**: two initial explicit inspections and two explicit keyboard-journey inspections after reload. All completed navigation/layout/disclosure/history/zoom windows generated **zero extra evidence POSTs** and **zero findings calls**. The log contains method/path/status output, without credentials, headers or bodies.

Temporary artifacts outside Git:

- `/private/tmp/opspilot-ux4-access.log` — combined access output from the two temporary backend runs.
- `/private/tmp/opspilot-ux4-desktop-1440.jpg` — focused case, retrieval action and first source below the header.
- `/private/tmp/opspilot-ux4-mobile-drawer-390.jpg` — open mobile drawer and visible focus.

The development server emitted the expected proxy error during the intentional backend stop. It also reported a hydration attribute warning showing browser-extension-added `data-new-gr-c-s-check-loaded`/`data-gr-ext-installed` attributes on `body`. A clean-profile reproduction was not performed; no application hydration defect is established by that warning, and no unrelated workaround was added.

## Remaining work and recommendation

No implementation blocker was observed in the bounded checks. Independent review and the unperformed screen-reader/text-only-zoom/cross-browser checks remain acceptance follow-ups. Recommend reviewing this uncommitted Increment 4 diff and completing those checks before full accessibility sign-off. Explain independently why modal focus needs deliberate return, why `aria-disabled` needs an activation guard, why closed disclosures can retain geometry, and why successful retrieval is separate from complete evidence.

Stop here. Task 5B and Git publication require separate authorization.

## Final acceptance and checkpoint authorization — 23 November 2026

The owner reports that Increment 4 passed independent Code Review and final QA, including re-verification of the resolved P2 hover-contrast defect. This supersedes earlier pending-review/QA-failure status for increment acceptance; the original observations and verification limits remain historical evidence. This Git checkpoint task does not independently repeat QA or claim full WCAG conformance.

Verified before staging: branch `codex/task-5ux-workspace-redesign`; local HEAD and existing remote feature-branch tip both `5e9ee8d4de2d4e76a595cd563b22b8e169ce54cc`, the approved Increment 3 parent. The complete tracked/untracked inventory matches the accepted **15-file** scope: **two documents, seven application/style files and six test/browser-check files**. The application/style files are `case-workspace.tsx`, `evidence-view.tsx`, `globals.css`, `investigation-panel.tsx`, `page.tsx`, `visitor-session-panel.tsx` and `workspace-shell.tsx`. The six test files are `case-navigation.test.mjs`, `evidence.test.mjs`, `hover-contrast.test.mjs`, `responsive-accessibility.browser.mjs`, `workspace-regressions.browser.mjs` and `workspace-shell.test.mjs`. The two documents are this report and Project Status.

Reviewed full application/test changes, the report/status content and all new files. The scope remains responsive/modal navigation, reflow, accessible focus/status/disclosures, guarded busy controls, the accepted contrast fix and focused regression evidence. No backend contracts, fixture changes, dependencies, live OpenAI, findings, human review, export or unrelated features are included. Credentials, generated artifacts, local configuration and temporary screenshots/logs remain outside the checkpoint. Checkpoint preparation updates only these two documents; application and test contents remain QA-approved and unchanged. Earlier 69-test/TypeScript/build/browser results are historical and are not rerun by this publication task.

Stage only the reviewed files, inspect the staged diff/content and run `git diff --cached --check` before committing. Authorized commit message: `feat(ux): complete responsive workspace and accessibility improvements`. Push only to the existing remote feature branch, then stop. No PR, merge, branch deletion, application code modification or Task 5B.
