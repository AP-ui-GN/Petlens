/**
 * Holds the chosen clip while the person reads the consent notes, so the
 * screen can be rebuilt without making them pick the video again.
 */

import type { ClipAsset } from './api';

export type PendingSelection = {
  clip: ClipAsset;
  petId: string | null;
  source: string;
  license: string;
  sourceUrl: string;
};

let pending: PendingSelection | null = null;

export function stashSelection(selection: PendingSelection) {
  pending = selection;
}

/** Returns the stashed selection once, then forgets it. */
export function takeSelection(): PendingSelection | null {
  const value = pending;
  pending = null;
  return value;
}

export function hasStashedSelection() {
  return pending !== null;
}
