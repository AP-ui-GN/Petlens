/**
 * Plain-language wording and retry rules for connection problems.
 * No React Native imports, so the tests can run it directly under Node.
 */

export type FailureKind = 'network' | 'timeout' | 'auth' | 'server' | 'unexpected' | 'not-petlens';

/** Automatic retries stop after this many tries; the person can still retry by hand. */
export const HEALTH_RETRY_DELAYS_MS = [1000, 2000, 4000, 8000, 16000] as const;

/** A sleeping free-tier host can need a while to wake, so give the check room. */
export const HEALTH_TIMEOUT_MS = 10_000;

export function nextHealthRetryDelay(autoRetriesSoFar: number): number | null {
  return HEALTH_RETRY_DELAYS_MS[autoRetriesSoFar] ?? null;
}

export function kindFromStatus(status: number): FailureKind {
  if (status === 401 || status === 403) return 'auth';
  if (status >= 500) return 'server';
  return 'unexpected';
}

export function describeHealthFailure(kind: FailureKind): string {
  switch (kind) {
    case 'network':
      return 'Unable to connect. Check your internet connection and try again.';
    case 'timeout':
      return 'The analysis server is taking too long to respond. It may be waking up, so try again in a moment.';
    case 'auth':
      return 'This version of the app is not allowed to use the analysis server. Please update the app.';
    case 'server':
      return 'The analysis server is having trouble right now. Please try again in a moment.';
    case 'not-petlens':
      return 'The address answered, but not like the PetLens analysis server.';
    case 'unexpected':
      return 'The analysis server did not respond as expected. Please try again in a moment.';
  }
}

/** Short heading for the connection banner. Only a network failure means "offline". */
export function connectionTitle(kind: FailureKind | null): string {
  if (kind === 'network') return 'Offline';
  return 'Server unavailable';
}

export type AnalysisFailure =
  | { kind: 'cancelled' }
  | { kind: 'network' }
  | { kind: 'unreadable' }
  | { kind: 'http'; status: number; serverMessage: string };

/**
 * Wording for a failed upload. A server message is only shown for client
 * errors (4xx), where it explains what is wrong with the clip. Server-side
 * errors never pass internal text through to the screen.
 */
export function describeAnalysisFailure(failure: AnalysisFailure, maxUploadMb: number): string {
  if (failure.kind === 'cancelled') return 'Analysis was cancelled.';
  if (failure.kind === 'network') {
    return 'Unable to connect. Check your internet connection and try again.';
  }

  if (failure.kind === 'unreadable') {
    return 'The analysis service returned a result the app could not read. Please try again.';
  }

  const { status, serverMessage } = failure;
  if (status === 413) {
    return `That clip is larger than the ${maxUploadMb} MB beta limit. Try a shorter clip.`;
  }
  if (status === 401 || status === 403) {
    return 'This version of the app is not allowed to use the analysis server. Please update the app.';
  }
  if (status === 504) return 'The analysis took too long. Try a shorter clip.';
  if (status >= 500) {
    return 'The analysis service could not finish this clip. Please try again in a moment.';
  }
  if (serverMessage.trim()) return serverMessage.trim();
  return 'This clip could not be analyzed. Please try a different video.';
}
