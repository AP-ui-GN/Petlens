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
  return (ids ?? []).flatMap((id) => {
    if (id === 'development') return [];
    const line = registry.entries.find((entry) => entry.id === id)?.resultLine;
    return line ? [line] : [];
  });
}
