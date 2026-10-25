import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizePetWeightsToPounds } from '../src/lib/walks.ts';
import type { Pet } from '../src/lib/types.ts';

const pet = (weight: string, weightUnit?: Pet['weightUnit']): Pet => ({
  id: 'pet-1',
  name: 'Mabel',
  species: 'Dog',
  breed: '',
  age: '',
  weight,
  weightUnit,
  notes: '',
  createdAt: '2026-01-01T00:00:00.000Z',
});

test('kilogram profile weights are converted and tagged as pounds once', () => {
  const migrated = normalizePetWeightsToPounds([pet('10', 'kg')]);
  assert.equal(migrated.changed, true);
  assert.equal(migrated.pets[0]?.weight, '22');
  assert.equal(migrated.pets[0]?.weightUnit, 'lb');

  const repeated = normalizePetWeightsToPounds(migrated.pets);
  assert.equal(repeated.changed, false);
  assert.equal(repeated.pets[0]?.weight, '22');
});

test('legacy mobile weights without a unit remain pounds', () => {
  const migrated = normalizePetWeightsToPounds([pet('62')]);
  assert.equal(migrated.pets[0]?.weight, '62');
  assert.equal(migrated.pets[0]?.weightUnit, 'lb');
});
