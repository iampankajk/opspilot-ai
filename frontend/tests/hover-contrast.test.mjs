import assert from 'node:assert/strict';
import { test } from 'node:test';
import { assertInteractionContrast } from './responsive-accessibility.browser.mjs';

const observation = changes => ({ selector: '.thread-nav button', hover: true, focusVisible: false,
  selected: false, disabled: false, samples: [{ text: 'Payment failures', ratio: 6.45 }], ...changes });

test('interaction contrast regression rejects the reproduced hover ratios and unrounded threshold failures', () => {
  for (const ratio of [1.09, 1.36, 1.69, 4.4999, NaN]) {
    assert.throws(() => assertInteractionContrast(observation({ samples: [{ text: 'Case text', ratio }] })), /below 4.5/);
  }
  assert.doesNotThrow(() => assertInteractionContrast(observation({ samples: [{ text: 'Case text', ratio: 4.5 }] })));
});

test('interaction contrast requires real hovered/focused/selected state observations and measured text', () => {
  assert.throws(() => assertInteractionContrast(observation({ hover: false }), { hover: true }), /Expected hover=true/);
  assert.throws(() => assertInteractionContrast(observation(), { focusVisible: true }), /Expected focusVisible=true/);
  assert.throws(() => assertInteractionContrast(observation(), { selected: true }), /Expected selected=true/);
  assert.throws(() => assertInteractionContrast(observation({ samples: [] })), /No text measured/);
  assert.doesNotThrow(() => assertInteractionContrast(observation({ focusVisible: true, selected: true }),
    { hover: true, focusVisible: true, selected: true, disabled: false }));
});

test('disabled control exemption does not excuse enabled but unselected navigation', () => {
  const low = { samples: [{ text: 'Unavailable', ratio: 2 }] };
  assert.doesNotThrow(() => assertInteractionContrast(observation({ ...low, disabled: true }), { disabled: true }));
  assert.throws(() => assertInteractionContrast(observation({ ...low, selected: false })), /below 4.5/);
});
