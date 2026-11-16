// Run through the connected browser's documented tab/viewport APIs.
// Precondition: Payment failures → Overview with CASE-FAIL-001 evidence explicitly
// retrieved. This checks the mounted application, native scrolling and real focus;
// it is intentionally separate from the dependency-free Node render tests.
export async function checkWorkspaceRegressions(tab, viewport) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const results = [];
  for (const size of [{ width: 1440, height: 900 }, { width: 1280, height: 800 }]) {
    await viewport.set(size);
    const target = tab.playwright.locator("#evidence-SYN-STRIPE-FAIL-001");
    const origin = tab.playwright.locator("#evidence-SYN-PO-ATT-001");
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
    const link = tab.playwright.locator('a[href="#evidence-SYN-STRIPE-FAIL-001"]').first();
    // Exercise both pointer and native keyboard activation at each viewport.
    for (const activation of ["pointer", "keyboard"]) {
      if (activation === "pointer") await link.click();
      else await link.press("Enter");
      await tab.playwright.domSnapshot();
      await target.locator("summary:focus").waitFor({ state: "visible", timeoutMs: 5000 });
      const geometry = await tab.playwright.evaluate(() => {
        const record = document.querySelector("#evidence-SYN-STRIPE-FAIL-001");
        const summary = record.querySelector("summary");
        const header = document.querySelector(".workspace-shell > .incident-header");
        return { top: summary.getBoundingClientRect().top, bottom: summary.getBoundingClientRect().bottom,
          headerBottom: header.getBoundingClientRect().bottom, open: record.open,
          focused: document.activeElement === summary,
          originOpen: document.querySelector("#evidence-SYN-PO-ATT-001").open };
      });
      assert(geometry.open && geometry.originOpen, "Target and originating record must remain expanded");
      assert(geometry.focused, "Relationship target summary must receive focus");
      assert(geometry.top >= geometry.headerBottom && geometry.bottom <= size.height,
        `Relationship summary must be visible below the header: ${JSON.stringify(geometry)}`);
      assert(new URL(await tab.url()).hash === "#evidence-SYN-STRIPE-FAIL-001", "Native URL fragment must be retained");
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
    await tab.playwright.getByRole("button", { name: "Go to Overview", exact: true }).press("Enter");
    await tab.playwright.domSnapshot();
    await tab.playwright.locator('.workspace-tabs button[aria-current="page"]:focus').waitFor({ state: "visible", timeoutMs: 5000 });
    assert(await overview.getAttribute("aria-current") === "page", "Overview must become current");
    assert(await tab.playwright.getByRole("button", { name: "Go to Overview", exact: true }).count() === 0,
      "Return control must be unmounted");
    assert(await tab.playwright.evaluate(() => document.activeElement === document.querySelector(".workspace-tabs button")),
      "Focus must remain on the mounted Overview button after the return control disappears");
    await overview.press("Tab");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement.textContent === "Evidence"),
      "Next Tab must follow the normal order to Evidence");
    await evidence.press("Shift+Tab");
    await tab.playwright.domSnapshot();
    assert(await tab.playwright.evaluate(() => document.activeElement === document.querySelector(".workspace-tabs button")),
      "Shift+Tab must return to Overview");
    results.push({ ...size, overviewFocusRestored: true, keyboardOrderPreserved: true });
  }
  return results;
}
