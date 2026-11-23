// Execute through the connected browser APIs, with real explicitly retrieved
// responses. DOM observations never inspect framework internals or trigger APIs.
export async function checkResponsiveLayout(tab, viewport, size) {
  await viewport.set(size);
  const result = await tab.playwright.evaluate(() => {
    const visible = node => !!node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    const shell = document.querySelector('.workspace-shell');
    const header = shell.querySelector(':scope > .incident-header');
    const panel = Array.from(shell.querySelectorAll('.evidence-panel')).find(visible);
    const overflow = Array.from(shell.querySelectorAll('*')).filter(visible).filter(n => {
      const rect = n.getBoundingClientRect();
      return rect.width > 0 && (rect.left < -1 || rect.right > innerWidth + 1);
    }).map(n => ({ tag: n.tagName, class: n.className }));
    const row = Array.from(shell.querySelectorAll('.case-row')).find(visible);
    return { width: innerWidth, height: innerHeight,
      pageOverflow: document.documentElement.scrollWidth > innerWidth,
      overflow, headerPosition: getComputedStyle(header).position,
      drawerTrigger: visible(shell.querySelector('.mobile-navigation-trigger')),
      desktopRail: visible(shell.querySelector('.workspace-rail')),
      thread: shell.querySelector('#thread-heading').textContent,
      case: Array.from(shell.querySelectorAll('.selected-case')).find(visible)?.innerText,
      caseColumns: row ? getComputedStyle(row).gridTemplateColumns : null,
      groups: panel?.querySelectorAll('.evidence-group').length,
      sources: panel?.querySelectorAll('[data-source]').length,
      records: panel?.querySelectorAll('.evidence-record').length,
      requests: Array.from(shell.querySelectorAll('.request-history')).map(n => n.textContent),
    };
  });
  if (result.pageOverflow || result.overflow.length) throw new Error(`Horizontal overflow: ${JSON.stringify(result)}`);
  if (result.width <= 720 && (!result.drawerTrigger || result.desktopRail)) throw new Error('Mobile navigation must replace the rail');
  if (result.width > 720 && (!result.desktopRail || result.drawerTrigger)) throw new Error('Desktop rail must remain available');
  if (result.groups !== undefined && (result.groups !== 4 || result.sources !== 6)) throw new Error('Responsive evidence lost source context');
  return result;
}

export async function checkMobileDrawer(tab, viewport, size) {
  await viewport.set(size);
  const trigger = tab.playwright.getByRole('button', { name: 'Threads & cases', exact: true });
  await trigger.press('Enter'); await tab.playwright.domSnapshot();
  const observe = () => tab.playwright.evaluate(() => ({
    modal: document.querySelector('dialog').matches(':modal'),
    inside: document.querySelector('dialog').contains(document.activeElement),
    focus: document.activeElement.textContent,
    expanded: document.querySelector('.mobile-navigation-trigger').getAttribute('aria-expanded'),
  }));
  const initial = await observe();
  if (!initial.modal || !initial.inside || initial.focus !== 'Close navigation') throw new Error('Drawer must open as a named modal with initial focus');
  await tab.pressKey(null, 'shift+Tab'); await tab.playwright.domSnapshot();
  const reverse = await observe();
  if (!reverse.inside || !/CASE-/.test(reverse.focus)) throw new Error('Reverse Tab must wrap to the last case');
  await tab.pressKey(null, 'Tab'); await tab.playwright.domSnapshot();
  if ((await observe()).focus !== 'Close navigation') throw new Error('Forward Tab must wrap to Close');
  await tab.pressKey(null, 'Escape'); await tab.playwright.domSnapshot();
  const escaped = await observe();
  if (escaped.modal || escaped.expanded !== 'false' || escaped.focus !== 'Threads & cases') throw new Error('Escape must dismiss and return focus');
  await trigger.press('Enter'); await tab.playwright.domSnapshot();
  await tab.playwright.getByRole('button', { name: 'Close navigation', exact: true }).press('Enter');
  await tab.playwright.domSnapshot();
  if ((await observe()).focus !== 'Threads & cases') throw new Error('Close must return invoking focus');
  return { size, initial, reverse, escaped, closeFocusReturned: true };
}

export async function inspectAccessibility(tab) {
  return tab.playwright.evaluate(() => {
    const visible = n => {
      if (!n.getClientRects().length || getComputedStyle(n).visibility === 'hidden') return false;
      if (n.matches('.skip-link:not(:focus)')) return false;
      for (let parent = n.parentElement; parent; parent = parent.parentElement) {
        if (parent.matches('details:not([open])') && !parent.querySelector(':scope > summary')?.contains(n)) return false;
      }
      return true;
    };
    const controls = Array.from(document.querySelectorAll('button, summary, input, a[href]')).filter(visible);
    const targets = controls.filter(n => !n.matches(':disabled')).map(n => {
      const r = n.getBoundingClientRect();
      return { name: n.getAttribute('aria-label') || n.textContent || n.getAttribute('id'), width: r.width, height: r.height,
        inline: n.tagName === 'A' && getComputedStyle(n).display === 'inline' };
    });
    const ids = Array.from(document.querySelectorAll('[id]')).map(n => n.id);
    return { mainLandmarks: document.querySelectorAll('main').length,
      duplicateIds: ids.filter((id, i) => ids.indexOf(id) !== i),
      unnamed: controls.filter(n => !n.getAttribute('aria-label') && !n.textContent.trim() && !n.labels?.length).map(n => n.outerHTML),
      undersized: targets.filter(n => !n.inline && (n.width < 24 || n.height < 24)),
      minimumTargetHeight: Math.min(...targets.filter(n => !n.inline).map(n => n.height)),
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      visibleStatusRegions: Array.from(document.querySelectorAll('[role="status"]')).filter(visible).length,
      targets: targets.length,
    };
  });
}

// A bounded rendered-text contrast check, not a complete WCAG audit. Disabled
// controls and clipped assistive text are excluded. Opaque ancestor backgrounds
// cover this application's colors; no gradients or images are used behind text.
export async function inspectTextContrast(tab) {
  return tab.playwright.evaluate(() => {
    const rgb = color => color.match(/[\d.]+/g)?.map(Number);
    const luminance = values => values.slice(0, 3).map(v => {
      v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
    }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const ratios = new Map();
    for (const node of document.querySelectorAll('main *')) {
      if (!Array.from(node.childNodes).some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())) continue;
      if (!node.getClientRects().length || node.closest(':disabled, .sr-only, .skip-link:not(:focus)')) continue;
      let visible = true;
      for (let p = node.parentElement; p; p = p.parentElement) {
        if (p.matches('details:not([open])') && !p.querySelector(':scope > summary')?.contains(node)) visible = false;
      }
      if (!visible) continue;
      const style = getComputedStyle(node), foreground = rgb(style.color);
      let background;
      for (let p = node; p; p = p.parentElement) {
        const color = rgb(getComputedStyle(p).backgroundColor);
        if (color && (color.length === 3 || color[3] === 1)) { background = color; break; }
      }
      if (!foreground || !background) continue;
      const a = luminance(foreground), b = luminance(background);
      const ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      const key = `${style.color} on ${background.slice(0, 3).join(',')}`;
      ratios.set(key, { colors: key, ratio: Math.round(ratio * 100) / 100, sample: node.textContent.slice(0, 80) });
    }
    const pairs = Array.from(ratios.values()).sort((a, b) => a.ratio - b.ratio);
    return { pairs, belowNormalTextAA: pairs.filter(p => p.ratio < 4.5), minimum: pairs[0]?.ratio };
  });
}

// Call after real pointer/keyboard actions. Unlike a default-state page scan,
// this samples every text color within one control against its painted ancestor
// background, and records the actual pseudo-classes so hover cannot be assumed.
export async function inspectInteractionContrast(tab, selector) {
  return tab.playwright.evaluate(selector => {
    const control = document.querySelector(selector);
    if (!control?.getClientRects().length) throw new Error(`Control is not visible: ${selector}`);
    const rgb = color => color.match(/[\d.]+/g)?.map(Number);
    const luminance = values => values.slice(0, 3).map(v => {
      v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
    }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const samples = [];
    for (const node of [control, ...control.querySelectorAll('*')]) {
      const text = Array.from(node.childNodes).filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent.trim()).join(' ').trim();
      if (!text || node.closest('.sr-only') || !node.getClientRects().length) continue;
      const color = getComputedStyle(node).color, foreground = rgb(color);
      let background;
      for (let parent = node; parent; parent = parent.parentElement) {
        const value = getComputedStyle(parent).backgroundColor, channels = rgb(value);
        if (channels && (channels.length === 3 || channels[3] === 1)) { background = value; break; }
      }
      if (!foreground || !background) throw new Error(`Unmeasured text colors: ${text}`);
      const a = luminance(foreground), b = luminance(rgb(background));
      samples.push({ text, color, background, ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) });
    }
    const style = getComputedStyle(control);
    return { selector, hover: control.matches(':hover'), focusVisible: control.matches(':focus-visible'),
      selected: control.getAttribute('aria-pressed') === 'true' || control.getAttribute('aria-current') === 'true' || control.getAttribute('aria-current') === 'page',
      disabled: control.matches(':disabled') || control.getAttribute('aria-disabled') === 'true',
      background: style.backgroundColor, color: style.color, borderColor: style.borderColor,
      boxShadow: style.boxShadow, outline: `${style.outlineWidth} ${style.outlineStyle} ${style.outlineColor}`, samples };
  }, selector);
}

export function assertInteractionContrast(result, expected = {}) {
  for (const [state, value] of Object.entries(expected)) {
    if (result[state] !== value) throw new Error(`Expected ${state}=${value}: ${result.selector}`);
  }
  if (!result.samples.length) throw new Error(`No text measured: ${result.selector}`);
  // Inactive (disabled) controls are exempt under SC 1.4.3; keep their measured
  // colors in the result so default/hover invariance can still be checked.
  if (!result.disabled && result.samples.some(s => !Number.isFinite(s.ratio) || s.ratio < 4.5)) {
    throw new Error(`Text contrast below 4.5:1: ${JSON.stringify(result)}`);
  }
  return result;
}
