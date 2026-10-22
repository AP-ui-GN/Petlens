/**
 * The observation stored for a finished walk.
 *
 * The server returns the rule-based note when no language-model rewrite ran.
 * `usedLlm: false` is that normal path. It is not a missing result, and it
 * must not be replaced with a generic "analysis completed" sentence.
 */
export function observationFromResult(result: { observation: string; usedLlm: boolean }): string {
  return result.observation;
}
