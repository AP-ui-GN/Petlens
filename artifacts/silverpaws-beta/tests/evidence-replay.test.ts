import assert from 'node:assert/strict';
import test from 'node:test';
import { boundedVideoTime, motionPoints, nearestMotionPoint, replayTimingMatches } from '../src/lib/evidence-replay.ts';

test('a 60-frame video has 59 interval midpoints, not 60 evenly stretched samples', () => {
  const points = Array.from({ length: 59 }, (_, index) => ({ timeSeconds: (index + 0.5) / 12, movement: 0.1 }));
  assert.equal(nearestMotionPoint(points, 0)?.timeSeconds, 0.5 / 12);
  assert.equal(nearestMotionPoint(points, 5)?.timeSeconds, 58.5 / 12);
  assert.ok(replayTimingMatches('decoder', points, 5));
});

test('source seconds are preserved for different frame rates and irregular timing', () => {
  for (const fps of [12, 24, 30000 / 1001, 60]) {
    const points = [{ timeSeconds: 0.5 / fps, movement: 0.01 }, { timeSeconds: 1.5 / fps, movement: 0.02 }];
    assert.equal(nearestMotionPoint(points, 1.5 / fps)?.timeSeconds, 1.5 / fps);
  }
  const irregular = [{ timeSeconds: 0.02, movement: 0.1 }, { timeSeconds: 0.08, movement: 0.2 }, { timeSeconds: 0.26, movement: 0.3 }];
  assert.equal(nearestMotionPoint(irregular, 0.24)?.timeSeconds, 0.26);
});

test('sparse and single-point traces snap to measured samples without invented values', () => {
  const sparse = [{ timeSeconds: 0.1, movement: 0 }, { timeSeconds: 4.8, movement: 0.9 }];
  assert.deepEqual(nearestMotionPoint(sparse, 4.7), sparse[1]);
  assert.deepEqual(nearestMotionPoint(sparse, -10), sparse[0]);
  assert.deepEqual(nearestMotionPoint([sparse[0]], 5), sparse[0]);
  assert.equal(nearestMotionPoint([], 3), undefined);
  assert.equal(nearestMotionPoint(sparse, NaN), undefined);
});

test('boundaries and missing media metadata never produce an invalid seek', () => {
  assert.equal(boundedVideoTime(-1, 5), 0);
  assert.equal(boundedVideoTime(99, 5), 5);
  assert.equal(boundedVideoTime(1.2345, 5), 1.2345);
  for (const duration of [0, -1, NaN, Infinity]) assert.equal(boundedVideoTime(3, duration), 0);
  assert.equal(boundedVideoTime(NaN, 5), 0);
});

test('missing, invalid, and nonincreasing times are not silently repaired', () => {
  for (const value of [undefined, null, [], [{ movement: 0.1 }], [{ timeSeconds: NaN, movement: 0.1 }],
    [{ timeSeconds: 0, movement: 2 }], [{ timeSeconds: 0.2, movement: 0.1 }, { timeSeconds: 0.1, movement: 0.2 }],
    [{ timeSeconds: 0, movement: 0.1 }, { timeSeconds: 0, movement: 0.2 }]]) {
    assert.deepEqual(motionPoints(value), []);
  }
});

test('legacy estimates, unknown origins and mismatched durations disable graph seeking', () => {
  const points = [{ timeSeconds: 0.1, movement: 0.2 }];
  for (const source of [undefined, 'nominal-fps', 'unavailable', 'other']) {
    assert.equal(replayTimingMatches(source, points, 5), false);
  }
  assert.equal(replayTimingMatches('decoder', [], 5), false);
  assert.equal(replayTimingMatches('decoder', points, 0), false);
  assert.equal(replayTimingMatches('decoder', [{ timeSeconds: 6, movement: 0.1 }], 5), false);
  assert.equal(replayTimingMatches('decoder', points, 5), true);
});
