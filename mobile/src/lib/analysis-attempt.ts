/**
 * One attempt to analyse a clip, kept free of React and native modules so the
 * retry behaviour can be tested directly.
 */

export type AttemptDeps<Clip extends { uri: string }, Result> = {
  isReadable: (uri: string) => Promise<boolean>;
  resolveUrl: () => Promise<string | null>;
  request: (baseUrl: string, clip: Clip, onUploadProgress: (fraction: number) => void) => Promise<Result>;
  describeError: (error: unknown) => string;
};

export type AttemptOutcome<Result> =
  | { kind: 'unreadable' }
  | { kind: 'no-server' }
  | { kind: 'failed'; message: string }
  | { kind: 'done'; result: Result };

/**
 * Check the clip can still be opened, then upload it. Retrying simply calls
 * this again with the same clip, so nothing is remembered between attempts.
 */
export async function attemptAnalysis<Clip extends { uri: string }, Result>(
  clip: Clip,
  deps: AttemptDeps<Clip, Result>,
  onUploadProgress: (fraction: number) => void = () => {},
): Promise<AttemptOutcome<Result>> {
  if (!(await deps.isReadable(clip.uri))) return { kind: 'unreadable' };

  try {
    const baseUrl = await deps.resolveUrl();
    if (!baseUrl) return { kind: 'no-server' };
    const result = await deps.request(baseUrl, clip, onUploadProgress);
    return { kind: 'done', result };
  } catch (error) {
    return { kind: 'failed', message: deps.describeError(error) };
  }
}

/**
 * Lets only one submission run at a time. React state updates too late to stop
 * two quick taps, so this is checked synchronously.
 */
export function createSubmissionGate() {
  let running = false;
  return {
    tryEnter(): boolean {
      if (running) return false;
      running = true;
      return true;
    },
    leave() {
      running = false;
    },
    get running() {
      return running;
    },
  };
}
