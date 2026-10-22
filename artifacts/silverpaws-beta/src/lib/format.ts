export function formatDate(date: string) {
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(date));
}

export function formatRelative(date: string) {
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  return `${days} days ago`;
}

/** Pose frames that cleared the confidence gate. A missing count is not shown as zero. */
export function formatPoseFrames(used: number | null | undefined, total: number | null | undefined) {
  if (typeof used !== 'number' || typeof total !== 'number') return 'Not measured';
  return `${used} of ${total}`;
}

export function formatDuration(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}