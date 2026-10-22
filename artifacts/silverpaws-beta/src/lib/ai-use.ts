/**
 * Lookup only. The sentences live in ai-use-registry.json, copied from
 * lib/ai-use/registry.json.
 */

import registry from './ai-use-registry.json' with { type: 'json' };

export type AiUseEntry = (typeof registry.entries)[number];

export function aiUseSummary(): string {
  return registry.summary;
}

export function aiUseEntries(): AiUseEntry[] {
  return registry.entries;
}

/** One quiet line per step that produced this walk. development is not a clip step. */
export function aiUseResultLines(ids: string[] | undefined): string[] {
  const byId = new Map(registry.entries.map((entry) => [entry.id, entry.resultLine]));
  return (ids ?? []).flatMap((id) => {
    if (id === 'development') return [];
    const line = byId.get(id);
    return line ? [line] : [];
  });
}
