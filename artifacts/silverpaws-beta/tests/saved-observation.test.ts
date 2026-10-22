import assert from 'node:assert/strict';
import test from 'node:test';

import { observationFromResult } from '../src/lib/saved-observation.ts';

test('a finished walk keeps the server note when no rewrite ran', () => {
  const observation = 'Picture motion was measured. Stride length was not measured.';
  const saved = observationFromResult({ observation, usedLlm: false });
  assert.equal(saved, observation);
  assert.equal(saved.includes('Gait analysis completed'), false);
});

test('an opencv-motion note is not relabeled as pose', () => {
  const observation = 'No pet pose landmarks were available for this clip, so stride symmetry was not measured.';
  const saved = observationFromResult({ observation, usedLlm: false });
  assert.equal(saved, observation);
  assert.equal(saved.toLowerCase().includes('pose model measured'), false);
});
