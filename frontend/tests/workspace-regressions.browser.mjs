// Run through the connected browser's documented tab/viewport APIs.
// Precondition: Payment failures → Evidence with CASE-FAIL-001 evidence explicitly
// retrieved. This checks the mounted application, native scrolling and real focus;
// it is intentionally separate from the dependency-free Node render tests.
export async function checkWorkspaceRegressions(tab, viewport) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]) {
    await viewport.set(size);
    const target = tab.playwright.locator('[id$="-SYN-STRIPE-FAIL-001"]');
    const origin = tab.playwright.locator('[id$="-SYN-PO-ATT-001"]');
    if (await target.getAttribute("open") !== null) {
      await target.locator("summary").press("Enter");
      await tab.playwright.domSnapshot();
    }
    if (await origin.getAttribute("open") === null) {
      await origin.locator("summary").press("Enter");
      await tab.playwright.domSnapshot();
    }
    const relationships = tab.playwright.locator(".evidence-panel > details")
      .filter({ hasText: "Record relationships and correlation explanations" });
    if (await relationships.getAttribute("open") === null) {
      await relationships.locator("summary").press("Enter");
      await tab.playwright.domSnapshot();
    }
    const link = tab.playwright.locator('a[href$="-SYN-STRIPE-FAIL-001"]').first();
    // Exercise both pointer and native keyboard activation at each viewport.
    for (const activation of ["pointer", "keyboard"]) {
      if (activation === "pointer") await link.click();
      else await link.press("Enter");
      await tab.playwright.domSnapshot();
      await target.locator("summary:focus").waitFor({ state: "visible", timeout: 5000 });
      const geometry = await tab.playwright.evaluate(() => {
        const record = document.querySelector('[id$="-SYN-STRIPE-FAIL-001"]');
        const summary = record.querySelector("summary");
        const header = document.querySelector(".workspace-shell > .incident-header");
        return { top: summary.getBoundingClientRect().top, bottom: summary.getBoundingClientRect().bottom,
          headerBottom: header.getBoundingClientRect().bottom, open: record.open,
          focused: document.activeElement === summary,
          originOpen: document.querySelector('[id$="-SYN-PO-ATT-001"]').open };
      });
      assert(geometry.open && geometry.originOpen, "Target and originating record must remain expanded");
      assert(geometry.focused, "Relationship target summary must receive focus");
      assert(geometry.top >= geometry.headerBottom && geometry.bottom <= size.height,
        `Relationship summary must be visible below the header: ${JSON.stringify(geometry)}`);
      assert(new URL(await tab.url()).hash.endsWith("-SYN-STRIPE-FAIL-001"), "Native URL fragment must be retained");
      results.push({ ...size, activation, ...geometry });
      await target.locator("summary").press("Enter");
      await tab.playwright.domSnapshot();
      assert(await target.getAttribute("open") === null, "Target must remain independently collapsible");
    }
    const overview = tab.playwright.getByRole("button", { name: "Overview", exact: true });
    const evidence = tab.playwright.getByRole("button", { name: "Evidence", exact: true });
    await evidence.press("Enter");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement.textContent === "Evidence"),
      "Unrelated view navigation must not move focus to Overview");
    await overview.press("Enter");
    await tab.playwright.domSnapshot();
    assert(await overview.getAttribute("aria-current") === "page", "Overview must become current");
    assert(await tab.playwright.getByRole("button", { name: "Open Evidence for CASE-FAIL-001", exact: true }).isVisible(),
      "Overview must restore the compact case row");
    await overview.press("Tab");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement.textContent === "Evidence"),
      "Next Tab must follow the normal order to Evidence");
    await evidence.press("Shift+Tab");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement === document.querySelector(".workspace-tabs button")),
      "Shift+Tab must return to Overview");
    await evidence.press("Enter");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.getByRole("button", { name: "Inspect again", exact: true }).isVisible(),
      "Evidence response must survive the Overview round trip");
    results.push({ ...size, localResultRetained: true, keyboardOrderPreserved: true });
  }
  return results;
}

// Precondition: both cases have one locally returned response and Payment failures
// is active. Native pointer input avoids the locator's preparatory scroll-to-center,
// which would change the very scroll position this regression is measuring.
export async function checkThreadContext(tab) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  async function clickThread(index) {
    const point = await tab.playwright.evaluate(i => {
      const rect = document.querySelectorAll(".thread-nav button")[i].getBoundingClientRect();
      return [rect.x + rect.width / 2, rect.y + rect.height / 2];
    }, index);
    await tab.click(point);
    await tab.playwright.domSnapshot();
  }
  const before = await tab.playwright.evaluate(() => ({ y: window.scrollY,
    history: Array.from(document.querySelectorAll('.evidence-panel > details:last-child')).map(n => n.textContent),
    expansions: Array.from(document.querySelectorAll('.evidence-panel details[id]')).map(n => [n.id, n.open]) }));
  await clickThread(1);
  const duplicate = await tab.playwright.evaluate(() => ({ y: window.scrollY,
    active: document.querySelector('#thread-heading').textContent,
    visible: Array.from(document.querySelectorAll('.evidence-panel')).filter(n => n.getBoundingClientRect().height > 0).map(n => n.getAttribute('aria-label')) }));
  assert(duplicate.active === "Possible duplicates" && duplicate.visible.join() === "Evidence for CASE-DUP-001", "Duplicate scope must be exclusive");
  await clickThread(0);
  const after = await tab.playwright.evaluate(() => ({ y: window.scrollY,
    history: Array.from(document.querySelectorAll('.evidence-panel > details:last-child')).map(n => n.textContent),
    expansions: Array.from(document.querySelectorAll('.evidence-panel details[id]')).map(n => [n.id, n.open]) }));
  assert(Math.abs(before.y - after.y) < 2, "Thread return must restore the original scroll position");
  assert(JSON.stringify(before.expansions) === JSON.stringify(after.expansions), "All record disclosures must retain their own state");
  assert(JSON.stringify(before.history) === JSON.stringify(after.history), "Navigation must retain exact local request identities");
  await tab.back(); await tab.playwright.domSnapshot();
  const back = await tab.playwright.evaluate(() => ({ thread: document.querySelector('#thread-heading').textContent, y: window.scrollY,
    focus: document.activeElement?.textContent }));
  assert(back.thread === "Possible duplicates" && Math.abs(back.y - duplicate.y) < 2, "Back must restore duplicate context/position");
  await tab.forward(); await tab.playwright.domSnapshot();
  assert(await tab.playwright.evaluate(() => document.querySelector('#thread-heading').textContent) === "Payment failures", "Forward must restore Payment failures");
  return { beforeY: before.y, afterY: after.y, duplicateY: duplicate.y, back,
    exactRequestHistoryRetained: true, disclosuresRetained: true };
}

// Review blockers 2/3. Precondition: one locally returned response for each seeded
// case. The requests themselves must be explicit before calling this function.
// These checks inspect retained UI/request IDs, never Next.js private state.
export async function checkReviewHistoryRegressions(tab, viewport) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];
  const snapshot = () => tab.playwright.evaluate(() => ({
    thread: document.querySelector('#thread-heading')?.textContent,
    view: document.querySelector('.workspace-tabs [aria-current]')?.textContent,
    requests: Array.from(document.querySelectorAll('.evidence-panel > details:last-child')).map(n => n.textContent),
    panels: document.querySelectorAll('.evidence-panel').length,
    y: window.scrollY,
  }));
  async function view(name) {
    await tab.playwright.getByRole('button', { name, exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
  }
  async function thread(name) {
    await tab.playwright.getByRole('button', { name: `${name} 1 configured case`, exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
  }
  async function traverse(direction) {
    await tab[direction]();
    await tab.playwright.domSnapshot();
  }
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]) {
    await viewport.set(size);
    await thread('Payment failures'); await view('Overview');
    await tab.playwright.getByRole('button', { name: 'Open Evidence for CASE-FAIL-001', exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
    const baseline = await snapshot();
    assert(baseline.panels === 2, 'Both returned Evidence panels must be retained before the history regression');
    const relationships = tab.playwright.getByRole('region', { name: 'Evidence for CASE-FAIL-001', exact: true })
      .locator('details').filter({ hasText: 'Record relationships and correlation explanations' });
    if (await relationships.getAttribute('open') === null) {
      await relationships.locator('summary').press('Enter'); await tab.playwright.domSnapshot();
    }
    const link = tab.playwright.locator('a[href$="-SYN-STRIPE-FAIL-001"]').first();
    await link.press('Enter'); await tab.playwright.domSnapshot();
    const fragment = new URL(await tab.url()).hash;
    assert(fragment.endsWith('-SYN-STRIPE-FAIL-001'), 'Relationship URL fragment must be preserved');
    await view('Overview'); await thread('Possible duplicates');
    await traverse('back');
    assert((await snapshot()).view === 'Overview' && (await snapshot()).thread === 'Payment failures', 'Back must restore the failure Overview');
    await traverse('back');
    const relationshipBack = await snapshot();
    assert(relationshipBack.view === 'Evidence' && relationshipBack.thread === 'Payment failures', 'Back must restore the selected failure case/view');
    assert(new URL(await tab.url()).hash === fragment, 'Back must restore the relationship fragment');
    const target = await tab.playwright.evaluate(() => {
      const node = document.querySelector('[id$="-SYN-STRIPE-FAIL-001"]');
      return { open: node?.open, focused: document.activeElement === node?.querySelector('summary'),
        top: node?.querySelector('summary').getBoundingClientRect().top,
        headerBottom: document.querySelector('.workspace-shell > .incident-header').getBoundingClientRect().bottom };
    });
    assert(target.open && target.focused && target.top >= target.headerBottom && target.top < size.height,
      `Relationship target must remain open/focused and visible after Back: ${JSON.stringify(target)}`);
    await traverse('forward'); assert((await snapshot()).view === 'Overview', 'Forward must restore Overview');
    await traverse('forward'); assert((await snapshot()).thread === 'Possible duplicates', 'Forward must restore the duplicate thread');
    let after = await snapshot();
    assert(after.panels === baseline.panels && JSON.stringify(after.requests) === JSON.stringify(baseline.requests),
      'Relationship/view/thread Back/Forward must not reload the document or lose returned panels/request identities');
    results.push({ ...size, relationshipHistoryRetained: true, target });

    await view('Overview');
    await tab.playwright.getByRole('button', { name: 'Open Evidence for CASE-DUP-001', exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
    for (const id of ['SYN-ZD-TICKET-002', 'SYN-ZD-ESCALATION-001']) {
      const record = tab.playwright.locator(`[id$="-${id}"]`);
      if (await record.getAttribute('open') === null) {
        await record.locator('summary').press('Enter'); await tab.playwright.domSnapshot();
      }
    }
    await tab.scroll([size.width - 80, size.height - 100], 'down', 2);
    await tab.playwright.domSnapshot();
    const evidence = await snapshot();
    assert(evidence.y > size.height, 'Evidence must be scrolled well below its context before native traversal');
    for (let cycle = 0; cycle < 2; cycle++) {
      await traverse('back'); assert((await snapshot()).view === 'Overview', 'Direct browser Back must restore Overview');
      await traverse('forward'); after = await snapshot();
      assert(after.view === 'Evidence' && after.thread === 'Possible duplicates', 'Direct browser Forward must restore duplicate Evidence');
      assert(Math.abs(after.y - evidence.y) < 2, `Forward must restore the outgoing Evidence position: expected ${evidence.y}, got ${after.y}`);
      assert(after.panels === baseline.panels && JSON.stringify(after.requests) === JSON.stringify(baseline.requests), 'Forward must retain both exact responses');
    }
    const expansions = await tab.playwright.evaluate(() => ['SYN-ZD-TICKET-002', 'SYN-ZD-ESCALATION-001']
      .map(id => document.querySelector(`[id$="-${id}"]`)?.open));
    assert(expansions.every(Boolean), 'Both Zendesk records must stay expanded');
    results.push({ ...size, forwardScrollExpected: evidence.y, forwardScrollActual: after.y,
      repeatedBackForward: true, panelsRetained: after.panels, expansions });
  }
  return results;
}

// Independent QA reproduction. Precondition: duplicate-case evidence was retrieved
// explicitly. All navigation below must reuse that response without another POST.
export async function checkRetainedEvidenceKeyboardFocus(tab, viewport, onRestored = async () => {}) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];
  async function goOverview() {
    await tab.playwright.getByRole('button', { name: 'Overview', exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
  }
  async function reopen() {
    await tab.playwright.getByRole('button', { name: 'Open Evidence for CASE-DUP-001', exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
  }
  async function tabToEvidence() {
    for (let i = 0; i < 8; i++) {
      if (await tab.playwright.evaluate(() => document.activeElement === document.querySelector('.workspace-tabs button:nth-child(2)'))) return;
      await tab.pressKey(null, 'Tab');
      await tab.playwright.domSnapshot();
    }
    throw new Error('Keyboard traversal did not reach Evidence');
  }
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]) {
    await viewport.set(size);
    await tab.playwright.getByRole('button', { name: 'Possible duplicates 1 configured case', exact: true }).press('Enter');
    await tab.playwright.domSnapshot();
    await goOverview(); await reopen();
    for (const id of ['SYN-ZD-TICKET-002', 'SYN-ZD-ESCALATION-001']) {
      const record = tab.playwright.locator(`[id$="-${id}"]`);
      if (await record.getAttribute('open') === null) {
        await record.locator('summary').press('Enter'); await tab.playwright.domSnapshot();
      }
    }
    // Exact QA sequence: Overview, reopen, scroll, Back, Tab to Evidence, Enter.
    await goOverview(); await reopen();
    await tab.scroll([size.width - 80, size.height - 100], 'down', 2);
    await tab.playwright.domSnapshot();
    const before = await tab.playwright.evaluate(() => ({ y: window.scrollY,
      requests: Array.from(document.querySelectorAll('.evidence-panel > details:last-child')).map(n => n.textContent) }));
    assert(before.y > size.height, 'QA regression requires deeply scrolled Evidence');
    await tab.back(); await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.querySelector('.workspace-tabs [aria-current]').textContent) === 'Overview', 'Back must restore Overview');
    await tabToEvidence();
    await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
    const after = await tab.playwright.evaluate(() => {
      const active = document.activeElement, rect = active.getBoundingClientRect();
      const headerBottom = document.querySelector('.workspace-shell > .incident-header').getBoundingClientRect().bottom;
      const panel = Array.from(document.querySelectorAll('.evidence-panel')).find(n => n.getBoundingClientRect().height > 0);
      return { y: window.scrollY, tag: active.tagName, text: active.textContent.slice(0, 130),
        inEvidence: panel?.contains(active), visible: rect.top >= Math.max(0, headerBottom) && rect.bottom <= window.innerHeight,
        top: rect.top, bottom: rect.bottom, headerBottom, focusVisible: active.matches(':focus-visible'),
        requests: Array.from(document.querySelectorAll('.evidence-panel > details:last-child')).map(n => n.textContent),
        expanded: ['SYN-ZD-TICKET-002', 'SYN-ZD-ESCALATION-001'].map(id => document.querySelector(`[id$="-${id}"]`)?.open) };
    });
    results.push({ ...size, expectedY: before.y, ...after });
    await onRestored(results.at(-1));
    // Collect both viewport observations before reporting the original failure.
    if (!after.inEvidence || !after.visible) continue;
    assert(Math.abs(after.y - before.y) < 2, 'Focus repair must not change retained scroll');
    assert(after.focusVisible, 'Restored keyboard focus must be visibly indicated');
    assert(after.expanded.every(Boolean) && JSON.stringify(after.requests) === JSON.stringify(before.requests), 'Record state and exact response identities must be retained');
    const sequence = await tab.playwright.evaluate(() => {
      const active = document.activeElement;
      const controls = Array.from(document.querySelectorAll('button, a[href], summary, input, [tabindex]'))
        .filter(n => n.tabIndex >= 0 && !n.disabled && n.getClientRects().length > 0 && !n.closest('[hidden]'));
      const order = Array.from(document.querySelectorAll('body *')), position = order.indexOf(active);
      const key = n => n && [n.tagName, n.id, n.textContent.slice(0, 130)].join('|');
      return { next: key(controls.find(n => order.indexOf(n) > position)),
        reverse: key(active.tabIndex >= 0 ? active : controls.filter(n => order.indexOf(n) < position).at(-1)) };
    });
    const activeKey = () => tab.playwright.evaluate(() => [document.activeElement.tagName, document.activeElement.id, document.activeElement.textContent.slice(0, 130)].join('|'));
    await tab.pressKey(null, 'Tab'); await tab.playwright.domSnapshot();
    assert(await activeKey() === sequence.next, 'Tab must continue to the next native control in document order');
    await tab.pressKey(null, 'shift+Tab'); await tab.playwright.domSnapshot();
    assert(await activeKey() === sequence.reverse, 'Shift+Tab must follow the native reverse order');
    // Pointer navigation keeps its own focus; it does not invoke keyboard repair.
    await tab.back(); await tab.playwright.domSnapshot();
    await tab.playwright.getByRole('button', { name: 'Evidence', exact: true }).click(); await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement === document.querySelector('.workspace-tabs button:nth-child(2)')), 'Pointer return must not steal focus into Evidence');
    results.at(-1).tabOrderPreserved = true;
    results.at(-1).pointerFocusPreserved = true;
  }
  assert(results.every(r => r.inEvidence && r.visible), `Retained Evidence focus must be visible inside Evidence: ${JSON.stringify(results)}`);
  return results;
}
