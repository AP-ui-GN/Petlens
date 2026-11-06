import assert from 'node:assert/strict';
import test from 'node:test';

import { buildAnalyticsCohorts, metricComparisons } from '../src/lib/analytics.ts';
import type { Analysis, Pet } from '../src/lib/storage.ts';

function pet(id = 'pet-1'): Pet {
  return {
    id,
    name: id,
    species: 'Dog',
    breed: '',
    age: '',
    weight: '',
    notes: '',
    createdAt: '2026-10-01T12:00:00.000Z',
  };
}

function walk(overrides: Partial<Analysis> & Pick<Analysis, 'id' | 'createdAt'>): Analysis {
  return {
    id: overrides.id,
    petId: 'pet-1',
    fileName: `${overrides.id}.mp4`,
    durationSeconds: 10,
    createdAt: overrides.createdAt,
    status: 'complete',
    pipeline: 'coco-pose',
    overallScore: 70,
    factors: { movementConsistency: 60, symmetry: 65 },
    ...overrides,
  };
}

test('analytics cohorts keep pets and measurement pipelines separate', () => {
  const cohorts = buildAnalyticsCohorts([
    walk({ id: 'old', createdAt: '2026-10-01T12:00:00.000Z' }),
    walk({ id: 'new', createdAt: '2026-10-02T12:00:00.000Z', pipeline: 'movenet', petId: 'pet-2' }),
    walk({ id: 'other-pet', createdAt: '2026-10-03T12:00:00.000Z', petId: 'pet-2' }),
    walk({ id: 'processing', createdAt: '2026-10-04T12:00:00.000Z', status: 'processing' }),
  ], [pet(), pet('pet-2')]);

  assert.equal(cohorts.length, 3);
  assert.deepEqual(cohorts.map((cohort) => cohort.points.map((point) => point.id)), [
    ['old'],
    ['other-pet'],
    ['new'],
  ]);
});

test('walkthrough compares scored walks and labels score rises and falls with signed deltas', () => {
  const [cohort] = buildAnalyticsCohorts([
    walk({ id: 'old', createdAt: '2026-10-01T12:00:00.000Z', overallScore: 70 }),
    walk({
      id: 'middle',
      createdAt: '2026-10-02T12:00:00.000Z',
      overallScore: null,
      factors: { movementConsistency: 65, symmetry: 65 },
    }),
    walk({
      id: 'new',
      createdAt: '2026-10-03T12:00:00.000Z',
      overallScore: 80,
      factors: { movementConsistency: 55, symmetry: 65 },
    }),
  ], [pet()]);

  assert.ok(cohort);
  const overall = metricComparisons(cohort).filter((comparison) => comparison.metric.key === 'overall');
  const consistency = metricComparisons(cohort).filter((comparison) => comparison.metric.key === 'consistency');

  assert.equal(overall.length, 1);
  assert.equal(overall[0]?.delta, 10);
  assert.equal(overall[0]?.previous.id, 'old');
  assert.equal(overall[0]?.current.id, 'new');
  assert.equal(consistency[0]?.delta, 5);
  assert.equal(consistency[1]?.delta, -10);
});
