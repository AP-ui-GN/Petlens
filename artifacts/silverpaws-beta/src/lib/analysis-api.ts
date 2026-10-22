/**
 * Front-end side of the analysis request.
 *
 * The generated client does the HTTP work. This module owns the two things the UI
 * needs on top of it: local checks that stop a doomed upload, and turning any
 * failure into a sentence a pet owner can act on.
 */

import {
  ApiError,
  analyzeMovementClip,
  type AnalyzeResult,
} from '@workspace/api-client-react';

/** Matches the beta limit on the server (MAX_UPLOAD_MB). */
export const MAX_UPLOAD_MB = 60;

/** Clips longer than this are rejected before upload to keep analysis responsive. */
export const MAX_CLIP_SECONDS = 120;

export const MIN_CLIP_SECONDS = 2;

export type ClipProblem = { field: 'type' | 'size' | 'duration'; message: string };

/**
 * Check a chosen file before it is uploaded.
 *
 * @param durationSeconds 0 when the browser could not read the metadata, which is
 * not treated as an error because the pipeline measures duration itself.
 */
export function checkClip(file: File, durationSeconds: number): ClipProblem | null {
  const looksLikeVideo =
    file.type.startsWith('video/') || /\.(mp4|mov|m4v|webm|avi|mkv)$/i.test(file.name);

  if (!looksLikeVideo) {
    return {
      field: 'type',
      message: 'Please choose a video file. MP4, MOV, and WebM work well for this beta.',
    };
  }

  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return {
      field: 'size',
      message: `That clip is larger than the ${MAX_UPLOAD_MB} MB beta limit. Try a shorter clip.`,
    };
  }

  if (durationSeconds > MAX_CLIP_SECONDS) {
    return {
      field: 'duration',
      message: `That clip is ${Math.round(durationSeconds)} seconds long. The server accepts up to ${MAX_CLIP_SECONDS} seconds. A useful walk is about 5 to 15 seconds.`,
    };
  }

  if (durationSeconds > 0 && durationSeconds < MIN_CLIP_SECONDS) {
    return {
      field: 'duration',
      message: `That clip is too short to compare frames. A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to ${MAX_CLIP_SECONDS} seconds.`,
    };
  }

  return null;
}

export type AnalysisRequest = {
  file: File;
  petName?: string;
  previousOverall?: number;
  previousPipeline?: string;
  signal?: AbortSignal;
};

export async function requestAnalysis({
  file,
  petName,
  previousOverall,
  previousPipeline,
  signal,
}: AnalysisRequest): Promise<AnalyzeResult> {
  return analyzeMovementClip(
    {
      video: file,
      ...(petName ? { petName } : {}),
      ...(previousOverall !== undefined ? { previousOverall } : {}),
      ...(previousPipeline ? { previousPipeline } : {}),
    },
    { signal },
  );
}

/**
 * Turn any thrown value into a message the UI can show directly.
 *
 * The server sends `{ ok: false, error }` for problems it can explain, so those
 * messages are preferred over anything generated here.
 */
export function describeAnalysisError(error: unknown): string {
  if (error instanceof ApiError) {
    const data = error.data as { error?: unknown } | null;
    if (data && typeof data.error === 'string' && data.error.trim()) {
      return data.error;
    }
    if (error.status === 413) {
      return `That clip is larger than the ${MAX_UPLOAD_MB} MB beta limit. Try a shorter clip.`;
    }
    if (error.status >= 500) {
      return 'The analysis service could not finish this clip. Please try again in a moment.';
    }
    return 'This clip could not be analyzed. Please try a different video.';
  }

  if (error instanceof DOMException && error.name === 'AbortError') {
    return 'Analysis was cancelled.';
  }

  if (error instanceof TypeError) {
    // fetch() throws TypeError when it cannot reach the server at all.
    return 'Could not reach the analysis service. Check that the API server is running.';
  }

  return 'Something went wrong while analyzing this clip. Please try again.';
}
