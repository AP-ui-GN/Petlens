/** Source seconds only: neither graph positions nor sample indices are frames. */
export type ReplayPoint = { timeSeconds: number; movement: number };
export type SessionVideo = { analysisId: string; file: File };

export function motionPoints(value: unknown): ReplayPoint[] {
  if (!Array.isArray(value)) return [];
  const points: ReplayPoint[] = [];
  for (const point of value) {
    if (!point || typeof point !== 'object' ||
        !Number.isFinite(point.timeSeconds) || point.timeSeconds < 0 ||
        !Number.isFinite(point.movement) || point.movement < 0 || point.movement > 1 ||
        (points.length > 0 && point.timeSeconds <= points[points.length - 1].timeSeconds)) return [];
    points.push({ timeSeconds: point.timeSeconds, movement: point.movement });
  }
  return points;
}

export function boundedVideoTime(time: number, duration: number): number {
  if (!Number.isFinite(time) || !Number.isFinite(duration) || duration <= 0) return 0;
  return Math.max(0, Math.min(duration, time));
}

/** Sparse traces snap to a measured interval midpoint; never interpolate values. */
export function nearestMotionPoint(points: ReplayPoint[], time: number): ReplayPoint | undefined {
  if (!Number.isFinite(time)) return undefined;
  return points.reduce<ReplayPoint | undefined>((nearest, point) =>
    !nearest || Math.abs(point.timeSeconds - time) < Math.abs(nearest.timeSeconds - time)
      ? point : nearest, undefined);
}

export function replayTimingMatches(
  timingSource: unknown, points: ReplayPoint[], duration: number,
): boolean {
  return timingSource === 'decoder' && points.length > 0 &&
    Number.isFinite(duration) && duration > 0 &&
    points.every((point) => point.timeSeconds <= duration + 0.0001);
}
