import assert from 'node:assert/strict';
import test from 'node:test';

import {
  COGNITIVE_MAX,
  cognitiveScore,
  dailyQualityOfLife,
  eveningSymptomNote,
  qualityTrend,
} from '../src/lib/daily-wellness.ts';

test('the weight total is the sum of the listed weights', () => {
  assert.equal(COGNITIVE_MAX, 14.5);
});

test('no selected symptoms score 100 and a full set scores 0', () => {
  assert.equal(cognitiveScore([]), 100);
  assert.equal(cognitiveScore([
    'disorientation', 'night-pacing', 'stuck', 'soiling', 'food',
    'anxiety', 'staring', 'withdrawn', 'day-sleeping', 'clingy',
  ]), 0);
});

test('a missing quality-of-life input is not scored as zero', () => {
  assert.equal(dailyQualityOfLife(80, null, 80), null);
  assert.equal(dailyQualityOfLife(80, 80, 80), 80);
});

test('evening wording waits for 30 logs and a 40 percent difference', () => {
  const quiet = Array.from({ length: 20 }, (_, index) => ({
    hourOfDay: index % 10,
    symptomIds: ['clingy'],
  }));
  const evening = Array.from({ length: 10 }, () => ({
    hourOfDay: 19,
    symptomIds: ['clingy', 'staring', 'withdrawn'],
  }));
  const few = eveningSymptomNote(quiet);
  assert.equal(few.show, false);
  const enough = eveningSymptomNote([...quiet, ...evening]);
  assert.equal(enough.show, true);
  assert.equal(enough.byHour[12], null);
});

test('the week comparison uses scored days and does not invent a zero', () => {
  const trend = qualityTrend([
    { day: '2026-10-21', score: 70 },
    { day: '2026-10-20', score: 70 },
    { day: '2026-10-19', score: 70 },
    { day: '2026-10-18', score: 80 },
    { day: '2026-10-17', score: 80 },
    { day: '2026-10-16', score: 80 },
    { day: '2026-10-15', score: 80 },
    { day: '2026-10-14', score: 85 },
  ], '2026-10-21');
  assert.equal(trend.label, 'declining');
  assert.equal(trend.lowerThanAWeekAgo, true);
});
