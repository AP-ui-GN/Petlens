/**
 * Talks to the PetLens analysis API (artifacts/api-server).
 *
 * Three jobs live here: work out where the API is, check a clip before it is
 * uploaded, and turn any failure into a sentence a pet owner can act on.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

import { chooseApiUrl } from './api-address';
import type { AnalyzeResult, Pipeline } from './types';

const API_URL_KEY = 'silverpaws:apiUrl';

/** Port the API server listens on by default (artifacts/api-server, PORT env). */
export const DEFAULT_API_PORT = 8080;

/** Matches the beta limit on the server (MAX_UPLOAD_MB). */
export const MAX_UPLOAD_MB = 60;
export const MAX_CLIP_SECONDS = 120;
export const MIN_CLIP_SECONDS = 2;

/** Give the pipeline time to finish before the phone gives up. */
const REQUEST_TIMEOUT_MS = 180_000;

// ---------------------------------------------------------------------------
// Where is the API?
// ---------------------------------------------------------------------------

/**
 * In Expo Go the JavaScript bundle is served from the developer's laptop, and
 * `hostUri` tells us that laptop's LAN address (for example "192.168.1.20:8081").
 * The API server usually runs on the same machine, so its address is the same
 * host on the API port. This is what makes the app work without any setup.
 */
export function guessApiUrl(): string | null {
  const hostUri = Constants.expoConfig?.hostUri;
  if (!hostUri) return null;
  const host = hostUri.split(':')[0];
  if (!host) return null;
  return `http://${host}:${DEFAULT_API_PORT}`;
}

/** Tidy a typed address: add http://, drop trailing slashes and a stray /api. */
export function normalizeApiUrl(input: string): string | null {
  let value = input.trim();
  if (!value) return null;
  if (!/^https?:\/\//i.test(value)) value = `http://${value}`;
  value = value.replace(/\/+$/, '').replace(/\/api$/i, '');
  // host[:port] with nothing else after the scheme
  if (!/^https?:\/\/[A-Za-z0-9.-]+(:\d{1,5})?$/.test(value)) return null;
  return value;
}

export async function getSavedApiUrl(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(API_URL_KEY);
  } catch {
    return null;
  }
}

export async function saveApiUrl(url: string | null) {
  try {
    if (url) await AsyncStorage.setItem(API_URL_KEY, url);
    else await AsyncStorage.removeItem(API_URL_KEY);
  } catch {
    // A failed save only means the next launch falls back to the guess.
  }
}

/** The public build setting. This value is visible in the app bundle. */
export function configuredApiUrl(): string | null {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  const fromExtra = Constants.expoConfig?.extra?.apiUrl;
  const raw = typeof fromEnv === 'string' && fromEnv.trim() ? fromEnv : fromExtra;
  if (typeof raw !== 'string' || !raw.trim()) return null;
  return normalizeApiUrl(raw);
}

/**
 * Saved Advanced address, then the build's EXPO_PUBLIC_API_URL.
 * Development with neither of those guesses the laptop from the Expo dev server.
 * A release build does not guess.
 */
export async function resolveApiUrl(): Promise<string | null> {
  const saved = await getSavedApiUrl();
  return chooseApiUrl({
    saved,
    configured: configuredApiUrl(),
    devGuess: guessApiUrl(),
    dev: typeof __DEV__ !== 'undefined' && __DEV__,
    devFallback: `http://localhost:${DEFAULT_API_PORT}`,
  });
}

export const MISSING_API_URL_MESSAGE =
  'This build has no analysis server address. A tester can set one under Settings, Advanced API address.';

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export type HealthOutcome = { ok: true } | { ok: false; message: string };

export async function checkHealth(baseUrl: string, timeoutMs = 5000): Promise<HealthOutcome> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}/api/healthz`, { signal: controller.signal });
    if (!response.ok) {
      return { ok: false, message: `The server answered with status ${response.status}.` };
    }
    const body = (await response.json()) as { status?: unknown };
    if (body.status !== 'ok') {
      return { ok: false, message: 'Something answered, but it does not look like the PetLens API.' };
    }
    return { ok: true };
  } catch (error) {
    if (isAbort(error)) return { ok: false, message: 'The server did not answer within 5 seconds.' };
    return {
      ok: false,
      message: 'Could not reach that address. Check the phone and laptop share a Wi-Fi network and the API server is running.',
    };
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Clip checks before upload
// ---------------------------------------------------------------------------

/** What the image picker gives us about the chosen video. */
export type ClipAsset = {
  uri: string;
  name: string;
  mimeType: string;
  sizeBytes: number | null;
  durationSeconds: number | null;
};

export type ClipProblem = { field: 'type' | 'size' | 'duration'; message: string };

export function checkClip(clip: ClipAsset): ClipProblem | null {
  const looksLikeVideo =
    clip.mimeType.startsWith('video/') || /\.(mp4|mov|m4v|webm|avi|mkv)$/i.test(clip.name);

  if (!looksLikeVideo) {
    return { field: 'type', message: 'Please choose a video. MP4 and MOV clips work well for this beta.' };
  }

  if (clip.sizeBytes !== null && clip.sizeBytes > MAX_UPLOAD_MB * 1024 * 1024) {
    return {
      field: 'size',
      message: `That clip is larger than the ${MAX_UPLOAD_MB} MB beta limit. Record a shorter clip or lower the camera quality.`,
    };
  }

  if (clip.durationSeconds !== null && clip.durationSeconds > MAX_CLIP_SECONDS) {
    return {
      field: 'duration',
      message: `That clip is ${Math.round(clip.durationSeconds)} seconds long. The server accepts up to ${MAX_CLIP_SECONDS} seconds. A useful walk is about 5 to 15 seconds.`,
    };
  }

  if (clip.durationSeconds !== null && clip.durationSeconds > 0 && clip.durationSeconds < MIN_CLIP_SECONDS) {
    return {
      field: 'duration',
      message: `That clip is too short to compare frames. A useful walk is about 5 to 15 seconds. The server accepts a longer clip, up to ${MAX_CLIP_SECONDS} seconds.`,
    };
  }

  return null;
}

// ---------------------------------------------------------------------------
// The analysis request
// ---------------------------------------------------------------------------

export class AnalysisError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'AnalysisError';
    this.status = status;
  }
}

export type AnalysisRequest = {
  baseUrl: string;
  clip: ClipAsset;
  petName?: string;
  previousOverall?: number;
  previousPipeline?: Pipeline;
  signal?: AbortSignal;
  /** Fraction of the clip uploaded so far, 0-1. */
  onUploadProgress?: (fraction: number) => void;
};

/**
 * Upload the clip and wait for the result.
 *
 * XMLHttpRequest is used instead of fetch because React Native reports upload
 * progress through it, and a 30 MB clip over Wi-Fi is slow enough that owners
 * need to see something moving.
 */
export function requestAnalysis(request: AnalysisRequest): Promise<AnalyzeResult> {
  const { baseUrl, clip, petName, previousOverall, previousPipeline, signal, onUploadProgress } = request;

  const form = new FormData();
  // React Native's FormData accepts a file descriptor object here.
  form.append('video', { uri: clip.uri, name: clip.name, type: clip.mimeType } as unknown as Blob);
  if (petName) form.append('petName', petName);
  if (previousOverall !== undefined) form.append('previousOverall', String(previousOverall));
  if (previousPipeline) form.append('previousPipeline', previousPipeline);

  return new Promise<AnalyzeResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${baseUrl}/api/analyze`);
    xhr.timeout = REQUEST_TIMEOUT_MS;
    xhr.responseType = 'text';

    const onAbort = () => xhr.abort();
    signal?.addEventListener('abort', onAbort);
    const cleanup = () => signal?.removeEventListener('abort', onAbort);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onUploadProgress?.(Math.min(1, event.loaded / event.total));
      }
    };

    xhr.onload = () => {
      cleanup();
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        if (isAnalyzeResult(body)) {
          resolve(body);
        } else {
          reject(new AnalysisError(502, 'The analysis service returned a result the app could not read.'));
        }
        return;
      }

      const serverMessage =
        body && typeof body === 'object' && typeof (body as { error?: unknown }).error === 'string'
          ? ((body as { error: string }).error)
          : '';
      reject(new AnalysisError(xhr.status, serverMessage));
    };

    xhr.onerror = () => {
      cleanup();
      reject(new TypeError('Network request failed'));
    };
    xhr.ontimeout = () => {
      cleanup();
      reject(new AnalysisError(504, 'The analysis took too long. Try a shorter clip.'));
    };
    xhr.onabort = () => {
      cleanup();
      reject(new AbortSignalError());
    };

    xhr.send(form);
  });
}

class AbortSignalError extends Error {
  constructor() {
    super('Aborted');
    this.name = 'AbortError';
  }
}

function isAbort(error: unknown) {
  return error instanceof Error && error.name === 'AbortError';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isNullableNumber(value: unknown) {
  return value === null || isFiniteNumber(value);
}

function hasOptionalNullableNumbers(record: Record<string, unknown>, keys: string[]) {
  return keys.every((key) => !(key in record) || isNullableNumber(record[key]));
}

/**
 * Check the response has the fields every screen relies on. This is the
 * mobile-side guard against a misbehaving server; the server validates the same
 * payload against the full OpenAPI schema before sending it.
 */
export function isAnalyzeResult(value: unknown): value is AnalyzeResult {
  if (!isRecord(value)) return false;
  const result = value;
  const measurements = isRecord(result.measurements) ? result.measurements : null;
  const factors = isRecord(result.factors) ? result.factors : null;
  const modelInfo = isRecord(result.modelInfo) ? result.modelInfo : null;
  const weights = result.weightsUsed === undefined ? null : isRecord(result.weightsUsed) ? result.weightsUsed : undefined;
  const validDiagnostics = result.diagnostics === undefined || isRecord(result.diagnostics);
  const poseKeypoints = measurements?.poseKeypoints;
  const validPoseKeypoints =
    poseKeypoints === undefined ||
    poseKeypoints === null ||
    (Array.isArray(poseKeypoints) &&
      poseKeypoints.every((point: unknown) => {
        if (!isRecord(point)) return false;
        const keypoint = point;
        return (
          typeof keypoint.name === 'string' &&
          typeof keypoint.x === 'number' && Number.isFinite(keypoint.x) && keypoint.x >= 0 && keypoint.x <= 1 &&
          typeof keypoint.y === 'number' && Number.isFinite(keypoint.y) && keypoint.y >= 0 && keypoint.y <= 1 &&
          typeof keypoint.confidence === 'number' &&
          Number.isFinite(keypoint.confidence) &&
          keypoint.confidence >= 0 &&
          keypoint.confidence <= 1
        );
      }));
  const validFactors = factors !== null && hasOptionalNullableNumbers(factors, [
    'movementConsistency',
    'symmetry',
    'mobility',
    'activity',
    'historicalChange',
  ]);
  const validWeights =
    weights === null ||
    (weights !== undefined &&
      ['movementConsistency', 'symmetry', 'mobility', 'activity', 'historicalChange']
        .every((key) => !(key in weights) || isFiniteNumber(weights[key])));
  const validMeasurements = measurements !== null &&
    isFiniteNumber(measurements.frameCount) &&
    isFiniteNumber(measurements.durationSeconds) &&
    isFiniteNumber(measurements.motionMean) &&
    isFiniteNumber(measurements.motionStd) &&
    isFiniteNumber(measurements.motionCoverage) &&
    typeof measurements.symmetryReliable === 'boolean' &&
    hasOptionalNullableNumbers(measurements, [
      'meanKeypointConfidence',
      'leftAnkleMotion',
      'rightAnkleMotion',
      'strideSymmetry',
      'asymmetryPercent',
      'hipStability',
    ]) &&
    validPoseKeypoints;
  return (
    result.ok === true &&
    (result.pipeline === 'dog-pose' || result.pipeline === 'movenet' || result.pipeline === 'opencv-motion') &&
    (result.signalQuality === 'good' || result.signalQuality === 'limited' || result.signalQuality === 'unusable') &&
    typeof result.signalNote === 'string' &&
    typeof result.observation === 'string' &&
    typeof result.limitations === 'string' &&
    typeof result.concerningChange === 'boolean' &&
    typeof result.usedLlm === 'boolean' &&
    validFactors &&
    validMeasurements &&
    (result.overallScore === undefined || isNullableNumber(result.overallScore)) &&
    (result.strideSymmetryScore === undefined || isNullableNumber(result.strideSymmetryScore)) &&
    (result.asymmetryPercent === undefined || isNullableNumber(result.asymmetryPercent)) &&
    (result.confidence === undefined || isNullableNumber(result.confidence)) &&
    validWeights &&
    modelInfo !== null &&
    (modelInfo.pipeline === 'dog-pose' || modelInfo.pipeline === 'movenet' || modelInfo.pipeline === 'opencv-motion') &&
    typeof modelInfo.modelName === 'string' &&
    typeof modelInfo.modelVersion === 'string' &&
    modelInfo.runsOn === 'server' &&
    isNullableNumber(result.modelConfidence) &&
    isNullableNumber(result.framesUsed) &&
    isNullableNumber(result.framesTotal) &&
    typeof result.lowConfidence === 'boolean' &&
    Array.isArray(result.qualityNotes) &&
    result.qualityNotes.every((note: unknown) => typeof note === 'string') &&
    Array.isArray(result.aiUse) &&
    result.aiUse.every((step: unknown) => typeof step === 'string') &&
    validDiagnostics
  );
}

/** Turn any thrown value into a message the UI can show directly. */
export function describeAnalysisError(error: unknown): string {
  if (error instanceof AnalysisError) {
    if (error.message.trim()) return error.message;
    if (error.status === 413) {
      return `That clip is larger than the ${MAX_UPLOAD_MB} MB beta limit. Try a shorter clip.`;
    }
    if (error.status >= 500) {
      return 'The analysis service could not finish this clip. Please try again in a moment.';
    }
    return 'This clip could not be analyzed. Please try a different video.';
  }

  if (isAbort(error)) return 'Analysis was cancelled.';

  if (error instanceof TypeError) {
    return 'Could not reach the analysis service. Check the API address in Settings and that the server is running.';
  }

  return 'Something went wrong while analyzing this clip. Please try again.';
}
