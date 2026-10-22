/**
 * Per-clip AI-use ids. The pipeline names the steps it ran. This module only
 * adds llm-rewrite when a validated rewrite was kept, and it never attaches
 * the development entry to a clip.
 */

const NOT_A_CLIP_STEP = new Set(["llm-rewrite", "development"]);

export function aiUseForResult(ids: readonly string[] | undefined, usedLlm: boolean): string[] {
  const base = (ids ?? []).filter((id) => !NOT_A_CLIP_STEP.has(id));
  if (usedLlm) base.push("llm-rewrite");
  return base;
}
