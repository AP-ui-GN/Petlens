import assert from 'node:assert/strict';
import test from 'node:test';

import { latestNoteHeadline } from '../src/lib/headline.ts';
import { hasStashedSelection, stashSelection, takeSelection } from '../src/lib/pending-selection.ts';

test('headline never says steady for a walk with no usable signal', () => {
  assert.equal(latestNoteHeadline({ signalQuality: 'unusable' }), 'No usable signal this time');
  assert.equal(latestNoteHeadline({ signalQuality: 'unusable', concerningChange: true }), 'No usable signal this time');
});

test('headline covers the other states', () => {
  assert.equal(latestNoteHeadline(null), 'Nothing to compare yet');
  assert.equal(latestNoteHeadline({ signalQuality: 'good' }), 'A steady picture');
  assert.equal(latestNoteHeadline({ signalQuality: 'limited' }), 'A limited picture');
  assert.equal(latestNoteHeadline({ signalQuality: 'good', lowConfidence: true }), 'A limited picture');
  assert.equal(latestNoteHeadline({ signalQuality: 'good', concerningChange: true }), 'A change worth a closer look');
});

test('a clip set aside for consent comes back exactly once', () => {
  const clip = { uri: 'file:///walk.mp4', name: 'walk.mp4', mimeType: 'video/mp4', sizeBytes: 10, durationSeconds: 8 };
  assert.equal(takeSelection(), null);
  stashSelection({ clip, petId: 'p1', source: 's', license: 'l', sourceUrl: 'u' });
  assert.equal(hasStashedSelection(), true);
  const restored = takeSelection();
  assert.deepEqual(restored?.clip, clip);
  assert.equal(restored?.petId, 'p1');
  assert.equal(takeSelection(), null);
});
