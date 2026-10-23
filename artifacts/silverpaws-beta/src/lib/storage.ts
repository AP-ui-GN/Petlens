/**
 * Local-first storage for pets and saved observations.
 *
 * The beta keeps every record in this browser. Nothing here talks to the network,
 * and every read is written so a missing or corrupted key cannot crash the app.
 */

import type {
  AnalysisFactors,
  AnalysisMeasurements,
  AnalysisWeights,
  AnalyzeResult,
} from '@workspace/api-client-react';
import type { CognitiveLog, HappinessEntry } from '@/lib/daily-wellness';

export type Pet = {
  id: string;
  name: string;
  species: string;
  breed: string;
  age: string;
  weight: string;
  notes: string;
  createdAt: string;
};

export type AnalysisStatus = 'complete' | 'processing' | 'ready';

export type Analysis = {
  id: string;
  petId: string;
  fileName: string;
  durationSeconds: number;
  createdAt: string;
  status: AnalysisStatus;
  strideSymmetryScore?: number | null;
  asymmetryPercent?: number | null;
  confidence?: number | null;
  observation?: string;
  limitations?: string;
  source?: string;
  license?: string;
  sourceUrl?: string;
  /** Which measurement path produced this record. New walks use coco-pose or opencv-motion. Older saved walks may use dog-pose or movenet. */
  pipeline?: string;
  signalQuality?: string;
  signalNote?: string;
  overallScore?: number | null;
  factors?: AnalysisFactors;
  measurements?: AnalysisMeasurements;
  weightsUsed?: AnalysisWeights;
  concerningChange?: boolean;
  usedLlm?: boolean;
  modelInfo?: {
    pipeline: string;
    modelName: string;
    modelVersion: string;
    runsOn: 'server';
  };
  /** Mean pose confidence from 0 to 1. Null means pose was not run, not zero. */
  modelConfidence?: number | null;
  framesUsed?: number | null;
  framesTotal?: number | null;
  lowConfidence?: boolean;
  qualityNotes?: string[];
  /** Registry ids for the steps that produced this walk. */
  aiUse?: string[];
  /** Demo results are held in memory and must never be added to saved history. */
  demo?: boolean;
};

/** The fields the app supplies itself, alongside the analysis result. */
export type ClipDetails = {
  petId: string;
  fileName: string;
  durationSeconds: number;
  source?: string;
  license?: string;
  sourceUrl?: string;
};

const PETS_KEY = 'silverpaws:pets';
const ANALYSES_KEY = 'silverpaws:analyses';
const COGNITIVE_KEY = 'silverpaws:cognitive-logs';
const HAPPINESS_KEY = 'silverpaws:happiness';

function read<T>(key: string, fallback: T): T {
  try {
    const value = window.localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write<T>(key: string, value: T) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Local-first beta should keep working even when storage is unavailable.
  }
}

export function getPets() {
  return read<Pet[]>(PETS_KEY, []);
}

export function getAnalyses() {
  return read<Analysis[]>(ANALYSES_KEY, []);
}

export function savePets(pets: Pet[]) {
  write(PETS_KEY, pets);
}

export function saveAnalyses(analyses: Analysis[]) {
  write(ANALYSES_KEY, analyses);
}

export function getCognitiveLogs() {
  return read<CognitiveLog[]>(COGNITIVE_KEY, []);
}

export function saveCognitiveLogs(logs: CognitiveLog[]) {
  write(COGNITIVE_KEY, logs);
}

export function getHappinessEntries() {
  return read<HappinessEntry[]>(HAPPINESS_KEY, []);
}

export function saveHappinessEntries(entries: HappinessEntry[]) {
  write(HAPPINESS_KEY, entries);
}

export function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

/**
 * Turn an API result into a saved record. Measurements and interpretation are
 * stored side by side but never merged, so a report can show them separately.
 */
export function toAnalysisRecord(
  result: AnalyzeResult,
  details: ClipDetails,
): Omit<Analysis, 'id' | 'createdAt'> {
  return {
    petId: details.petId,
    fileName: details.fileName,
    // The pipeline measures duration from the decoded frames; the browser value is
    // the fallback for containers where the frame rate could not be read.
    durationSeconds: Math.round(result.measurements.durationSeconds || details.durationSeconds),
    status: 'complete',
    pipeline: result.pipeline,
    signalQuality: result.signalQuality,
    signalNote: result.signalNote,
    overallScore: result.overallScore ?? null,
    factors: result.factors,
    measurements: result.measurements,
    weightsUsed: result.weightsUsed,
    strideSymmetryScore: result.strideSymmetryScore ?? null,
    asymmetryPercent: result.asymmetryPercent ?? null,
    confidence: result.confidence ?? null,
    observation: result.observation,
    limitations: result.limitations,
    concerningChange: result.concerningChange,
    usedLlm: result.usedLlm,
    modelInfo: result.modelInfo,
    modelConfidence: result.modelConfidence,
    framesUsed: result.framesUsed,
    framesTotal: result.framesTotal,
    lowConfidence: result.lowConfidence,
    qualityNotes: result.qualityNotes,
    aiUse: result.aiUse,
    source: details.source?.trim() || undefined,
    license: details.license?.trim() || undefined,
    sourceUrl: details.sourceUrl?.trim() || undefined,
  };
}

/**
 * Find the most recent scored walk for one pet, used as the trend baseline.
 * Only clips measured the same way can be compared, so the pipeline travels with
 * the score.
 */
export function findBaseline(analyses: Analysis[], petId: string) {
  const previous = analyses.find(
    (analysis) =>
      analysis.petId === petId &&
      typeof analysis.overallScore === 'number' &&
      Boolean(analysis.pipeline),
  );

  if (!previous || typeof previous.overallScore !== 'number') return undefined;
  return { overallScore: previous.overallScore, pipeline: previous.pipeline as string };
}

/** The score to show for a saved record, preferring the overall indicator. */
export function displayScore(analysis: Analysis): number | null {
  if (typeof analysis.overallScore === 'number') return analysis.overallScore;
  if (typeof analysis.strideSymmetryScore === 'number') return analysis.strideSymmetryScore;
  return null;
}
