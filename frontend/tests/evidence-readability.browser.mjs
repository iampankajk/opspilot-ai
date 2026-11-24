// Run with the connected browser's documented APIs after explicit inspection of
// the active seeded case. expectedPayloads is read from the frozen fixture by the
// local test runner; page evaluation inspects rendered DOM only.
export async function checkEvidenceReadability(tab, expectedCounts, expectedPayloads) {
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const before = await tab.playwright.evaluate(() => {
    const panel = Array.from(document.querySelectorAll('.evidence-panel')).find(n => n.getBoundingClientRect().height > 0);
    return { groups: Array.from(panel.querySelectorAll('.evidence-group')).map(n => ({
      label: n.getAttribute('aria-label'), count: n.querySelector('.evidence-group-heading > span').textContent,
      records: n.querySelectorAll('.evidence-record').length })),
      sources: panel.querySelectorAll('[data-source]').length,
      payloadsClosed: Array.from(panel.querySelectorAll('.original-payload')).every(n => !n.open),
      records: Array.from(panel.querySelectorAll('.evidence-record')).map(n => ({
        id: n.id, summary: n.querySelector(':scope > summary').textContent,
        payload: JSON.parse(n.querySelector('.original-payload pre').textContent) })),
      provider: panel.querySelector('[data-source="stripe"]').textContent,
      noMatches: Array.from(panel.querySelectorAll('[data-source="loki"], [data-source="tempo"]')).map(n => n.textContent),
      ticketOrder: Array.from(panel.querySelectorAll('.evidence-record')).map(n => n.id).filter(id => /SYN-ZD-TICKET-002|SYN-ZD-ESCALATION-001/.test(id)),
      notice: panel.querySelector('.evidence-notice')?.textContent,
      review: document.querySelector('.selected-case:not([hidden])')?.textContent,
    };
  });
  assert(before.groups.length === 4 && before.sources === 6, 'Four groups/six outcomes must remain visible');
  assert(JSON.stringify(before.groups.map(g => g.records)) === JSON.stringify(expectedCounts), 'Baseline group counts must remain exact');
  assert(before.payloadsClosed, 'Original payloads must be closed by default');
  assert(/unverified/.test(before.provider) && /bank-posting evidence are not constructed/.test(before.provider), 'Provider completeness and bank gap must stay local');
  for (const record of before.records) {
    const id = Object.keys(expectedPayloads).find(id => record.id.endsWith(`-${id}`));
    assert(id && Object.keys(record.payload).length === Object.keys(expectedPayloads[id]).length &&
      Object.entries(expectedPayloads[id]).every(([key, value]) => JSON.stringify(record.payload[key]) === JSON.stringify(value)), `Payload fidelity: ${record.id}`);
    assert(record.summary.includes('Why related') && /Timezone:|timestamp not supplied/.test(record.summary), 'Collapsed summaries must expose association and time');
  }
  if (expectedCounts[0] === 2) {
    assert(before.ticketOrder[0].endsWith('SYN-ZD-TICKET-002') && before.ticketOrder[1].endsWith('SYN-ZD-ESCALATION-001'), 'Zendesk 10:33 ticket must precede 10:40 escalation');
    assert(before.noMatches.every(text => /No matching records/.test(text)), 'Loki/Tempo zero outcomes must remain distinct');
    assert(/Multiple payment attempts/.test(before.notice), 'Duplicate interpretation notice must stay visible');
    await checkDuplicateCaution(tab);
  }
  const panel = tab.playwright.locator('.evidence-panel').filter({ visible: true });
  const first = panel.locator('.evidence-record').first();
  if (await first.getAttribute('open') === null) {
    await first.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  }
  const details = await first.innerText();
  assert(/Amount\/currency|Provider|Reported issue|Internal/.test(details), 'Readable labelled details must precede payload');
  const original = first.locator('.original-payload');
  await original.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  assert(await original.getAttribute('open') !== null, 'Original payload must be inspectable');
  await original.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  const explanations = await first.locator('.related-records a').all();
  for (const link of explanations) assert(await link.getAttribute('aria-describedby'), 'Every contextual link needs its relationship explanation');
  return { counts: before.groups.map(g => g.records), sixOutcomes: true, exactPayloads: before.records.length,
    rawClosedByDefault: true, readableDetails: true, localProviderLimitations: true, chronology: before.ticketOrder };
}

// Covers the whole visible workspace, including the thread description and any
// case/evidence content. innerText excludes hidden threads/views/disclosures.
// Run before and after explicit retrieval, at the selected case's entry position.
export async function checkDuplicateCaution(tab, requireInViewport = false) {
  const observation = await tab.playwright.evaluate(() => {
    const workspace = document.querySelector('.workspace-shell');
    const notice = Array.from(workspace.querySelectorAll('.evidence-notice')).find(n => n.getBoundingClientRect().height > 0);
    const bounds = notice?.getBoundingClientRect();
    const headerBottom = workspace.querySelector(':scope > .incident-header').getBoundingClientRect().bottom;
    return {
      cautionCount: (workspace.innerText.match(/multiple (?:payment )?attempts do not (?:establish|necessarily mean) multiple (?:customer )?charges/gi) ?? []).length,
      notice: notice?.innerText,
      visibleInContext: !!bounds && bounds.top >= Math.max(0, headerBottom) && bounds.bottom <= window.innerHeight,
    };
  });
  if (observation.cautionCount !== 1) throw new Error('The complete visible workspace must contain exactly one duplicate interpretation caution');
  if (!/Independent financial evidence.*bank\/settlement records.*may still be missing/.test(observation.notice ?? ''))
    throw new Error('The case/evidence caution must preserve the independent financial-evidence gap');
  if (requireInViewport && !observation.visibleInContext) throw new Error('The caution must be visible at the selected-case entry position');
  return observation;
}

export async function checkTechnicalDisclosures(tab) {
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const panel = tab.playwright.locator('.evidence-panel').filter({ visible: true });
  const record = panel.locator('.evidence-record').first();
  if (await record.getAttribute('open') === null) {
    await record.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  }
  const labels = ['Identifiers and source fields', 'Case association and matched fields', 'Original timestamps and provenance'];
  const opened = [];
  for (const label of labels) {
    const disclosure = record.locator('.record-content > details').filter({ hasText: label });
    if (await disclosure.getAttribute('open') === null) {
      await disclosure.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
    }
    const text = await disclosure.innerText();
    assert(await disclosure.getAttribute('open') !== null && text.length > label.length + 20, `Technical disclosure: ${label}`);
    opened.push({ label, text });
    await disclosure.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  }
  const attribution = record.locator('.record-relationship .evidence-disclosure').first();
  await attribution.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  const relationship = await attribution.innerText();
  assert(/Attribution:.*application-labelled relationship/.test(relationship), 'Original relationship attribution must be readable');
  assert(/Basis record: SYN-/.test(relationship) && /Category:/.test(relationship), 'Relationship basis/category must remain inspectable');
  await attribution.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  const group = tab.playwright.locator('.evidence-group').filter({ visible: true }).first();
  const scope = group.locator(':scope > .source-metadata');
  await scope.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  const sourceText = await scope.innerText();
  assert(/Scope:/.test(sourceText) && /Match status: matches/.test(sourceText), 'Original source scope/match details must be readable');
  await scope.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  return { nativeKeyboardDisclosures: labels, relationshipBasisAndAttribution: true, sourceScopeAndMatch: true,
    minutePrecisionPreserved: /Precision: minute/.test(opened[2].text), provenancePreserved: /Constructed synthetic fixture/.test(opened[2].text) };
}

export async function checkNativeEvidenceKeyboardJourney(tab) {
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const panel = tab.playwright.locator('.evidence-panel').filter({ visible: true });
  const first = panel.locator('.evidence-record').first();
  if (await first.getAttribute('open') !== null) {
    await first.locator(':scope > summary').press('Enter'); await tab.playwright.domSnapshot();
  }
  await tab.playwright.getByRole('button', { name: 'Inspect again', exact: true }).press('Tab');
  await tab.playwright.domSnapshot();
  let current = await tab.playwright.evaluate(() => ({ text: document.activeElement.textContent, list: document.activeElement.parentElement.className }));
  assert(current.list === 'source-records', 'Tab from inspection must reach the first source record-list summary');
  await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
  await tab.pressKey(null, 'Tab'); await tab.playwright.domSnapshot();
  assert(await tab.playwright.evaluate(() => document.activeElement.parentElement.classList.contains('source-metadata')), 'Collapsed list must skip its records');
  await tab.pressKey(null, 'shift+Tab'); await tab.playwright.domSnapshot();
  await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
  await tab.pressKey(null, 'Tab'); await tab.playwright.domSnapshot();
  const origin = await tab.playwright.evaluate(() => document.activeElement.parentElement.id);
  assert(origin.startsWith('evidence-'), 'Reopened list must put its first record in the native Tab order');
  await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
  await tab.pressKey(null, 'Tab'); await tab.playwright.domSnapshot();
  const related = await tab.playwright.evaluate(() => ({ tag: document.activeElement.tagName,
    href: document.activeElement.getAttribute('href'), explanation: document.getElementById(document.activeElement.getAttribute('aria-describedby'))?.textContent }));
  assert(related.tag === 'A' && related.href?.startsWith('#evidence-') && related.explanation, 'Tab must reach a related record with an associated explanation');
  await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
  const target = await tab.playwright.evaluate(id => ({ id: document.activeElement.parentElement.id,
    open: document.activeElement.parentElement.open, originOpen: document.getElementById(id).open,
    top: document.activeElement.getBoundingClientRect().top,
    bottom: document.activeElement.getBoundingClientRect().bottom,
    headerBottom: document.querySelector('.workspace-shell > .incident-header').getBoundingClientRect().bottom,
    height: window.innerHeight }), origin);
  assert(target.id === related.href.slice(1) && target.open && target.originOpen, 'Native Enter must reveal/focus target and preserve origin');
  assert(target.top >= target.headerBottom && target.bottom <= target.height, 'Keyboard relationship focus must be fully visible');
  await tab.pressKey(null, 'Return'); await tab.playwright.domSnapshot();
  assert(await tab.playwright.evaluate(() => !document.activeElement.parentElement.open), 'Target must collapse independently with Enter');
  return { nativeTabAndShiftTab: true, sourceCollapseAndReopen: true, origin, target: target.id,
    targetFocusVisible: true, independentCollapse: true };
}
