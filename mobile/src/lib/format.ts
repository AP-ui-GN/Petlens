import type { AnalysisFactors } from './types.ts';

export const FACTOR_LABELS: { key: keyof AnalysisFactors; label: string; help: string }[] = [
  { key: 'movementConsistency', label: 'Movement consistency', help: 'How steady the amount of movement stayed between frames.' },
  { key: 'symmetry', label: 'Stride symmetry', help: 'How similar the left and right leg movement looked.' },
  { key: 'mobility', label: 'Mobility', help: 'Hip steadiness and stride balance, when pose landmarks were reliable enough to measure.' },
  { key: 'activity', label: 'Activity', help: 'Share of the clip that contained visible movement.' },
  { key: 'historicalChange', label: 'Change from baseline', help: 'How this walk compares with the previous walk measured the same way. A first walk is not scored.' },
];

export const SIGNAL_LABELS: Record<string, string> = {
  good: 'Good signal',
  limited: 'Limited signal',
  unusable: 'No usable signal',
};

export const PIPELINE_LABELS: Record<string, string> = {
  'dog-pose': 'COCO-17 output (canine interpretation unvalidated)',
  movenet: 'Pose landmarks (MoveNet)',
  'opencv-motion': 'Picture motion only',
};

/** Format a measurement, keeping "not measured" visibly different from zero. */
export function formatMeasure(value: number | null | undefined, suffix = '', digits = 3) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not measured';
  return `${Number(value.toFixed(digits))}${suffix}`;
}

/** Pose frames that cleared the confidence gate. Null on either side stays "Not measured". */
export function formatPoseFrames(used: number | null | undefined, total: number | null | undefined) {
  if (typeof used !== 'number' || typeof total !== 'number') return 'Not measured';
  return `${used} of ${total}`;
}

export function formatScore(value: number | null | undefined) {
  return typeof value === 'number' ? `${Math.round(value)}` : '—';
}

export function formatDuration(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) return 'Unknown length';
  const whole = Math.round(seconds);
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

export function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Unknown date';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function formatDateTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'Unknown date';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function formatBytes(bytes: number | null) {
  if (bytes === null || !Number.isFinite(bytes)) return 'Unknown size';
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
