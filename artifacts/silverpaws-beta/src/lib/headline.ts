/**
 * Title for the "Latest mobility note" card. A walk with no usable signal
 * must never be called "steady"; it has nothing to say about steadiness.
 */

export type HeadlineInput = {
  signalQuality?: string | null;
  lowConfidence?: boolean | null;
  concerningChange?: boolean | null;
};

export function latestNoteHeadline(latest: HeadlineInput | null | undefined): string {
  if (!latest) return "Nothing to compare yet";
  if (latest.signalQuality === "unusable") return "No usable signal this time";
  if (latest.concerningChange) return "A change worth a closer look";
  if (latest.signalQuality === "limited" || latest.lowConfidence) return "A limited picture";
  return "A steady picture";
}
