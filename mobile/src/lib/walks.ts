/**
 * Rules for saved walks. Demo rows are not walks, and two pipelines are never
 * compared as if they were the same measurement.
 */

import type { Analysis } from './types.ts';

export const SAMPLE_WALK_ID = 'sample-walk';

export const VET_SUMMARY_LIMIT = 8;

export type WeightUnit = 'kg' | 'lb';

/** Unit shown on a pet form. Old phone profiles were labeled lb and are not treated as kg. */
export function weightUnitForPet(stored: WeightUnit | undefined, preference: WeightUnit, isNew: boolean): WeightUnit {
  if (stored === 'kg' || stored === 'lb') return stored;
  if (isNew) return preference;
  return 'lb';
}

const KG_PER_LB = 0.45359237;

function formatConvertedWeight(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/**
 * Change the unit of a typed weight. An empty field changes unit with no number.
 * A real number is converted and the sentence says both values. A non-number is
 * refused so an old pound value is never quietly relabeled as kilograms.
 */
export function applyWeightUnitChange(
  value: string,
  from: WeightUnit,
  to: WeightUnit,
): { ok: true; value: string; note: string | null } | { ok: false; note: string } {
  if (from === to) return { ok: true, value, note: null };
  const trimmed = value.trim();
  if (!trimmed) return { ok: true, value, note: null };
  const number = Number(trimmed);
  if (!Number.isFinite(number) || number <= 0) {
    return {
      ok: false,
      note: 'Enter the weight as a positive number before changing the unit, so the old number is not relabeled.',
    };
  }
  const converted = from === 'lb' ? number * KG_PER_LB : number / KG_PER_LB;
  const shown = formatConvertedWeight(converted);
  return {
    ok: true,
    value: shown,
    note: `${trimmed} ${from} is now ${shown} ${to}. The number was converted. It was not relabeled.`,
  };
}

/** Shown while an older profile still has no stored unit. */
export function legacyWeightNote(stored: WeightUnit | undefined, weight: string): string | null {
  if (stored === 'kg' || stored === 'lb') return null;
  if (!weight.trim()) return null;
  return 'This weight was saved before a unit was stored. It stays in pounds. It is not treated as kilograms.';
}

export function isDemoWalk(walk: { id?: string; demo?: boolean } | null | undefined): boolean {
  return Boolean(walk && (walk.demo || walk.id === SAMPLE_WALK_ID));
}

/** Saved walks only. Sample data is dropped even if it was written by mistake. */
export function realWalks(walks: Analysis[]): Analysis[] {
  return walks.filter((walk) => !isDemoWalk(walk));
}

export function walksForPet(walks: Analysis[], petId: string): Analysis[] {
  return realWalks(walks).filter((walk) => walk.petId === petId);
}

/**
 * Why two walks cannot be shown side by side, or null when they can.
 * Different pipelines are refused. Demo rows are refused.
 */
export function compareBlockReason(left: Analysis, right: Analysis): string | null {
  if (isDemoWalk(left) || isDemoWalk(right)) {
    return 'Sample data is not a saved walk, so it is not compared with a real one.';
  }
  if (left.id === right.id) {
    return 'Choose two different saved walks.';
  }
  if (left.pipeline !== right.pipeline) {
    return 'These walks were measured in different ways, so they are not shown side by side.';
  }
  return null;
}

/** Newest first, real walks only, capped for the vet summary. */
export function recentWalks(walks: Analysis[], limit = VET_SUMMARY_LIMIT): Analysis[] {
  return realWalks(walks)
    .slice()
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, limit);
}
